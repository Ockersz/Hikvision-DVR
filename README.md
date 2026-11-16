# Hikvision / EZVIZ Cloud to Local RTSP Bridge

A lightweight, production-ready relay bridge that transforms remote **Hikvision & EZVIZ DVRs/NVRs/IP Cameras** (connected behind standard dynamic NAT/firewalls without static IPs or port forwarding) into permanent, standardized **local RTSP endpoints**.

Any existing RTSP software (VLC, OpenCV, Home Assistant, Blue Iris, Frigate, go2rtc, FFmpeg) can consume your cameras locally as if the DVR were on the same LAN.

---

## 🏗️ Architecture

```
┌─────────────────────────────────┐
│ Remote DVR / NVR (Behind NAT)   │
│ DS-7116, iDS-7116, EZVIZ, etc.  │
└────────────────┬────────────────┘
                 │ Outbound P2P Tunnel
                 ▼
┌─────────────────────────────────┐
│ Hikvision / EZVIZ Cloud CDN     │
│ (open.ezvizlife.com / OpenAPI)  │
└────────────────┬────────────────┘
                 │ Dynamic Expiring Cloud HLS Stream
                 ▼
┌────────────────────────────────────────────────────────┐
│ Local Machine (Windows / Ubuntu Linux / Docker)        │
│                                                        │
│  ┌───────────────────────┐    API Updates              │
│  │     hik_bridge.py     ├──────────────────────┐      │
│  │ (Auto-Token & Stream) │                      │      │
│  └───────────────────────┘                      ▼      │
│                                           ┌───────────┐│
│                                           │  MediaMTX ││
│                                           │  (RTSP    ││
│                                           │   Server) ││
│                                           └─────┬─────┘│
└─────────────────────────────────────────────────┼──────┘
                                                  │ Local Static RTSP
                                                  ▼
                  ┌──────────────────────────────────────────────┐
                  │ rtsp://127.0.0.1:8554/hik_cam<Channel>       │
                  │ (VLC, OpenCV, Home Assistant, Frigate, etc.) │
                  └──────────────────────────────────────────────┘
```

---

## ✨ Features

- **No Static IP or Port Forwarding Required:** Works 100% through Hikvision/EZVIZ cloud relay.
- **Permanent Local RTSP URLs:** Your RTSP clients connect to a fixed local URL (`rtsp://127.0.0.1:8554/hik_camX`) that never changes even when cloud security tokens rotate.
- **Automated Token & Link Renewal:** Automatically negotiates 7-day access tokens and refreshes cloud stream URLs before expiration.
- **Cross-Platform:** Native support for **Windows** and **Ubuntu / Debian Linux** (as well as macOS & Docker).
- **Multi-Channel Mapping:** Expose any number of DVR camera channels concurrently (`hik_cam1`, `hik_cam2`, `hik_cam5`, etc.).
- **Zero CPU Re-Encoding:** MediaMTX re-muxes the cloud video packets natively without CPU-intensive transcoding.

---

## 🚀 Step-by-Step Setup

### 1. Clone & Install Dependencies

```bash
git clone https://github.com/your-username/hikvision-rtsp-bridge.git
cd hikvision-rtsp-bridge
```

Create a virtual environment and install Python dependencies:

**On Windows:**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**On Ubuntu / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### 2. Install MediaMTX

[MediaMTX](https://github.com/bluenviron/mediamtx) is the zero-dependency, high-performance RTSP server used to relay the video.

#### Option A: Windows
1. Download `mediamtx_vX.X.X_windows_amd64.zip` from [MediaMTX Releases](https://github.com/bluenviron/mediamtx/releases/latest).
2. Extract `mediamtx.exe` into this project folder.
3. Verify `mediamtx.yml` has API and RTSP enabled:
   ```yaml
   api: true
   apiAddress: 127.0.0.1:9997
   rtsp: true
   rtspAddress: :8554
   ```

#### Option B: Ubuntu / Debian Linux
```bash
# Download and extract latest MediaMTX for Linux x86_64
wget https://github.com/bluenviron/mediamtx/releases/download/v1.21.4/mediamtx_v1.21.4_linux_amd64.tar.gz
tar -xvzf mediamtx_v1.21.4_linux_amd64.tar.gz
chmod +x mediamtx

# Ensure API is enabled in mediamtx.yml
sed -i 's/^api: false/api: true/' mediamtx.yml
```

---

### 3. Configure Credentials (`.env`)

Copy the template:
```bash
# Windows
copy .env.example .env

# Linux
cp .env.example .env
```

Open `.env` and fill in your details:

```ini
# ==============================================================================
# HIKVISION / EZVIZ CLOUD TO RTSP BRIDGE CONFIGURATION
# ==============================================================================

# Mode: False for live DVR streaming, True to test with a public mock stream
HIK_MOCK_MODE=False

# Primary Developer API Credentials (from open.ezvizlife.com or open.hik-connect.com)
HIK_APP_KEY=your_app_key_here
HIK_APP_SECRET=your_app_secret_here

# Target DVR Serial Number (from the device sticker, e.g. D22115206)
HIK_DEVICE_SERIAL=D22115206

# Channels to expose as RTSP endpoints (comma-separated list, e.g. 5 or 1,2,5)
HIK_CHANNELS=5

# Stream Quality: 1 = Main Stream (HD / 1080p), 2 = Sub-Stream (SD / 480p)
HIK_STREAM_QUALITY=2

# Regional Cloud OpenAPI Host
# EZVIZ Open Platform: https://open.ezvizlife.com
# Hik-Connect TPP:     https://open.hik-connect.com
HIK_BASE_URL=https://open.ezvizlife.com

# MediaMTX Server Endpoints
MEDIAMTX_HOST=127.0.0.1
MEDIAMTX_API_PORT=9997
MEDIAMTX_RTSP_PORT=8554
```

> [!TIP]
> **Where to get AppKey & Secret:**
> 1. Log into the [EZVIZ Developer Console](https://isgpopen.ezviz.com/console/home.html) (Asia/Singapore) or [EZVIZ Europe Console](https://ieuopen.ezviz.com/console/home.html) using the primary owner account.
> 2. Navigate to **Account Settings** $\rightarrow$ **AppKey Management** to view/generate your `AppKey` and `AppSecret`.
> 3. Make sure to use the **primary owner's account** (the account that originally bound the DVR), not a shared guest account.

---

### 4. Run the Bridge

Open two terminal windows:

#### Terminal 1: Start MediaMTX
**Windows:**
```powershell
.\mediamtx.exe
```

**Ubuntu / Linux:**
```bash
./mediamtx
```

#### Terminal 2: Start the Python Bridge
**Windows:**
```powershell
python hik_bridge.py
```

**Ubuntu / Linux:**
```bash
python3 hik_bridge.py
```

Expected output:
```text
=================================================================
 Hikvision / EZVIZ Cloud to Local RTSP Relay Bridge
 Mode:           LIVE (Cloud OpenAPI)
 Target Device:  D22115206
 Channels:       [5]
 Stream Quality: 2 (Sub-Stream / SD)
 Cloud Gateway:  https://open.ezvizlife.com
=================================================================
[OK] Obtained accessToken (valid for 167 hours)

--- Syncing 1 channel(s) (MOCK_MODE=False) ---
[READY] RTSP Endpoint active: rtsp://127.0.0.1:8554/hik_cam5

[INFO] All streams active. Next link renewal in 45 minutes.
```

---

## 📺 Connecting Existing RTSP Software

Point your player or application directly to:
```text
rtsp://127.0.0.1:8554/hik_cam<ChannelNumber>
```

### 1. Test Playback with FFplay
```bash
ffplay -rtsp_transport tcp rtsp://127.0.0.1:8554/hik_cam5
```
*(Tip: Always specify `-rtsp_transport tcp` to avoid UDP packet drops).*

### 2. Embed into OpenCV (Python)
```python
import cv2

RTSP_URL = "rtsp://127.0.0.1:8554/hik_cam5"
# Force TCP transport for reliable low-latency frames
cap = cv2.VideoCapture(f"{RTSP_URL}?rtsp_transport=tcp")

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        continue
    cv2.imshow("Live DVR Camera", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
```

### 3. Embed into Home Assistant / Frigate / Blue Iris
- **Stream URL:** `rtsp://<bridge-ip>:8554/hik_cam5`
- **Protocol:** `TCP`
- **Authentication:** None (MediaMTX runs unauthenticated on localhost by default).

---

## ⚙️ Multi-Camera Configuration

To stream multiple cameras from the same DVR simultaneously, specify comma-separated channel numbers in `.env`:

```ini
HIK_CHANNELS=1,2,5,8
```

The bridge will automatically create dedicated RTSP endpoints for each camera:
- `rtsp://127.0.0.1:8554/hik_cam1`
- `rtsp://127.0.0.1:8554/hik_cam2`
- `rtsp://127.0.0.1:8554/hik_cam5`
- `rtsp://127.0.0.1:8554/hik_cam8`

---

## 🛠️ Troubleshooting

| Issue / Error | Cause | Resolution |
| :--- | :--- | :--- |
| `ErrCode 9053_0.ts` in video stream | The requested camera channel has no physical video input or that stream quality is disabled on the DVR. | 1. Switch `HIK_STREAM_QUALITY` in `.env` (try `1` for Main Stream or `2` for Sub-stream).<br>2. Confirm the camera is physically connected to that BNC port. |
| `code: 20018: The user doesn't own the device` | The AppKey belongs to an account where the DVR was shared as a guest. | Generate the `AppKey` and `AppSecret` using the **primary master account** that initially scanned the DVR's QR code. |
| `code: 20007: The device is offline` | DVR has lost power or internet connection at the remote site. | The script will automatically retry every 15s until the DVR reconnects. |
| `non-existing PPS 0 referenced` in player | Player started before receiving the first keyframe (I-frame). | Normal behavior during the first 1–2 seconds of an HLS/RTSP handshake. Provide 2-3 seconds for buffer synchronization. |

---

## 🔒 Security Best Practice

Never commit your `.env` file to version control. The included `.gitignore` automatically excludes:
- `.env` and `.env.*`
- Binary executables (`mediamtx.exe`, `mediamtx`)
- Recorded video fragments and logs
