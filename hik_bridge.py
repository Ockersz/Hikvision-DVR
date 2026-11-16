#!/usr/bin/env python3
"""
Hikvision / EZVIZ Cloud to Local RTSP Relay Bridge
===================================================
Bridges remote Hikvision / EZVIZ DVRs behind NAT/dynamic IP into standard,
local RTSP endpoints (via MediaMTX) for VLC, OpenCV, Home Assistant,
Blue Iris, Frigate, go2rtc, or any standard RTSP software.

Compatible with: Windows, Linux (Ubuntu/Debian), macOS, and Docker.
"""

import os
import sys
import time
import requests

# ==============================================================================
# ENVIRONMENT LOADER (Built-in; no external dotenv dependency required)
# ==============================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(filepath: str):
    """Loads key=value pairs into os.environ if not already defined."""
    if not os.path.isfile(filepath):
        return
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip()
            if not (val.startswith('"') or val.startswith("'")) and "#" in val:
                val = val.split("#", 1)[0].strip()
            val = val.strip("'\"")
            if key not in os.environ or not os.environ[key]:
                os.environ[key] = val


# Load .env file from project directory
load_env_file(os.path.join(BASE_DIR, ".env"))

# ==============================================================================
# CONFIGURATION
# ==============================================================================
MOCK_MODE = os.getenv("HIK_MOCK_MODE", "False").lower() in ("true", "1", "yes")

APP_KEY = os.getenv("HIK_APP_KEY", "")
APP_SECRET = os.getenv("HIK_APP_SECRET", "")
DEVICE_SERIAL = os.getenv("HIK_DEVICE_SERIAL", "")

# Channels to expose (comma-separated, e.g. "1" or "1,2,5")
raw_channels = os.getenv("HIK_CHANNELS", "1")
CHANNELS = [int(c.strip()) for c in raw_channels.split(",") if c.strip().isdigit()]

# Quality: 1 = Main Stream (HD), 2 = Sub-Stream (SD)
STREAM_QUALITY = int(os.getenv("HIK_STREAM_QUALITY", "1"))

# Regional Cloud OpenAPI Host
HIK_BASE_URL = os.getenv("HIK_BASE_URL", "https://open.ezvizlife.com").rstrip("/")

# MediaMTX REST API & RTSP Endpoints
MEDIAMTX_HOST = os.getenv("MEDIAMTX_HOST", "127.0.0.1")
MEDIAMTX_API_PORT = int(os.getenv("MEDIAMTX_API_PORT", "9997"))
MEDIAMTX_RTSP_PORT = int(os.getenv("MEDIAMTX_RTSP_PORT", "8554"))
MEDIAMTX_API = f"http://{MEDIAMTX_HOST}:{MEDIAMTX_API_PORT}/v3/config/paths"

# Public mock test stream (used only when HIK_MOCK_MODE=True)
MOCK_STREAM_URL = "https://test-streams.mux.dev/x36xhzz/x36xhzz.m3u8"

# Dynamic URL refresh interval (seconds) - Cloud URLs are valid for 24 hours
URL_REFRESH_INTERVAL = 2700  # 45 minutes


class HikvisionCloudBridge:
    def __init__(self):
        self.access_token = None
        self.token_expire_time = 0

    def get_access_token(self) -> str:
        """Fetches and caches the OpenAPI accessToken."""
        # Return cached token if valid for at least another 5 minutes
        if self.access_token and time.time() < (self.token_expire_time - 300):
            return self.access_token

        if not APP_KEY or not APP_SECRET:
            sys.exit(
                "[ERROR] HIK_APP_KEY and HIK_APP_SECRET must be configured in .env or environment variables."
            )

        url = f"{HIK_BASE_URL}/api/lapp/token/get"
        payload = {"appKey": APP_KEY, "appSecret": APP_SECRET}

        try:
            resp = requests.post(url, data=payload, timeout=10).json()
        except Exception as exc:
            raise RuntimeError(f"Network error while requesting token: {exc}")

        if resp.get("code") != "200":
            raise RuntimeError(f"Token fetch failed: {resp.get('msg')} (code {resp.get('code')})")

        data = resp["data"]
        self.access_token = data["accessToken"]
        self.token_expire_time = data["expireTime"] / 1000.0
        remaining_sec = int(self.token_expire_time - time.time())
        print(f"[OK] Obtained accessToken (valid for {remaining_sec // 3600} hours)")
        return self.access_token

    def get_live_stream_url(self, channel_no: int) -> str | None:
        """Requests the live stream address for a specific DVR camera channel."""
        if MOCK_MODE:
            print(f"[MOCK] Channel {channel_no}: returning test HLS stream URL...")
            return MOCK_STREAM_URL

        token = self.get_access_token()
        url = f"{HIK_BASE_URL}/api/lapp/v2/live/address/get"
        payload = {
            "accessToken": token,
            "deviceSerial": DEVICE_SERIAL,
            "channelNo": channel_no,
            "protocol": 2,  # 2 = HLS (.m3u8), standard format consumed by MediaMTX
            "quality": STREAM_QUALITY,
        }

        try:
            resp = requests.post(url, data=payload, timeout=10).json()
        except Exception as exc:
            raise RuntimeError(f"Network error while requesting channel {channel_no} stream: {exc}")

        code = resp.get("code")
        if code == "20007":
            print(f"[OFFLINE] Device {DEVICE_SERIAL} is currently offline on the cloud.")
            return None

        if code == "20018":
            raise RuntimeError(
                f"Device {DEVICE_SERIAL} ownership error: The account associated with this AppKey does not own the device. "
                "Ensure you are using the primary owner's AppKey."
            )

        if code != "200":
            raise RuntimeError(
                f"Stream fetch failed for Channel {channel_no}: {resp.get('msg')} (code {code})"
            )

        stream_url = resp["data"]["url"]
        return stream_url

    def update_mediamtx_source(self, stream_path: str, source_url: str):
        """Registers or updates the dynamic stream URL in MediaMTX."""
        patch_url = f"{MEDIAMTX_API}/patch/{stream_path}"
        add_url = f"{MEDIAMTX_API}/add/{stream_path}"
        config_payload = {"source": source_url, "sourceOnDemand": True}

        try:
            resp = requests.patch(patch_url, json=config_payload, timeout=5)
            if resp.status_code == 404:
                resp = requests.post(add_url, json=config_payload, timeout=5)

            if resp.status_code not in (200, 201):
                raise RuntimeError(f"MediaMTX API returned status {resp.status_code}: {resp.text}")

            print(
                f"[READY] RTSP Endpoint active: rtsp://{MEDIAMTX_HOST}:{MEDIAMTX_RTSP_PORT}/{stream_path}"
            )
        except requests.exceptions.ConnectionError:
            raise RuntimeError(
                f"Cannot connect to MediaMTX API at {MEDIAMTX_API}. "
                "Ensure MediaMTX is running and API is enabled on port 9997."
            )

    def sync_channels(self) -> bool:
        """Syncs all configured channels with MediaMTX. Returns True if any channel is live."""
        print(f"\n--- Syncing {len(CHANNELS)} channel(s) (MOCK_MODE={MOCK_MODE}) ---")
        active_count = 0
        for ch in CHANNELS:
            stream_path = f"hik_cam{ch}"
            try:
                stream_url = self.get_live_stream_url(ch)
                if stream_url:
                    self.update_mediamtx_source(stream_path, stream_url)
                    active_count += 1
            except Exception as e:
                print(f"[WARN] Channel {ch} error: {e}")

        return active_count > 0


def main():
    print("=" * 65)
    print(" Hikvision / EZVIZ Cloud to Local RTSP Relay Bridge")
    print(f" Mode:           {'MOCK (Public test stream)' if MOCK_MODE else 'LIVE (Cloud OpenAPI)'}")
    print(f" Target Device:  {DEVICE_SERIAL or '(Not set)'}")
    print(f" Channels:       {CHANNELS}")
    print(f" Stream Quality: {'1 (Main Stream / HD)' if STREAM_QUALITY == 1 else '2 (Sub-Stream / SD)'}")
    print(f" Cloud Gateway:  {HIK_BASE_URL}")
    print("=" * 65)

    if not DEVICE_SERIAL and not MOCK_MODE:
        sys.exit("[ERROR] HIK_DEVICE_SERIAL is not configured. Please set it in .env")

    bridge = HikvisionCloudBridge()

    while True:
        try:
            success = bridge.sync_channels()
            if success:
                print(f"\n[INFO] All streams active. Next link renewal in {URL_REFRESH_INTERVAL // 60} minutes.")
                time.sleep(URL_REFRESH_INTERVAL)
            else:
                print("\n[WAIT] DVR is offline or unreachable. Retrying in 15 seconds...\n")
                time.sleep(15)
        except KeyboardInterrupt:
            print("\n[STOP] Shutting down bridge gracefully.")
            sys.exit(0)
        except Exception as e:
            print(f"\n[ERROR] Sync loop error: {e}")
            print("[INFO] Retrying in 15 seconds...\n")
            time.sleep(15)


if __name__ == "__main__":
    main()
