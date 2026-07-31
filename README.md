# 🎵 Vibe - Spotify Downloader

**Ultimate Spotify Downloader with Web UI & Android App**

Everything merged and unified into one production-ready project.

---

## ✨ Status

✅ **Server Running** → http://localhost:8081
✅ **Configuration** → vibe-config.json
✅ **Deno Enabled** → YouTube downloads supported
✅ **Downloads** → vibe/downloads/
✅ **Android App** → Ready to build

---

## 🚀 Features

- ✓ Download Spotify tracks (MP3/M4A/FLAC/Opus)
- ✓ Download YouTube videos (Deno enabled)
- ✓ Real-time download logs
- ✓ Web interface on port 8081
- ✓ Android app (WebView wrapper)
- ✓ File browser & ZIP packs
- ✓ Customizable admin panel
- ✓ Docker containerized
- ✓ Batch downloads support

---

## 🎯 Quick Start

### Web Interface
```
http://localhost:8081
```

### Download a Track
1. Paste Spotify link or YouTube URL
2. Choose format (MP3/M4A/FLAC/Opus)
3. Click Download
4. Watch real-time log

### Mobile Access (Same WiFi)
```
http://YOUR_PC_IP:8081
```

---

## 🔧 Configuration

**Active Config:** `vibe-config.json`

```json
{
    "title": "Vibe",
    "tagline": "Spotify Downloader",
    "accent": "#ff2e88",
    "bg": "#050505",
    "port": 8081,
    "deno_enabled": true,
    "features": {
        "spotify_downloads": true,
        "youtube_downloads": true,
        "deno_support": true,
        "batch_downloads": true
    }
}
```

**Edit & Restart:**
```bash
nano vibe-config.json
docker compose restart
```

---

## 📱 Android App

Build APK:
1. Open Android Studio
2. File → Open → `vibe/android`
3. Build → Build APK(s)
4. APK: `android/build/outputs/apk/debug/app-debug.apk`

---

## 🐳 Docker Commands

```bash
# Start
docker compose up -d

# Stop
docker compose down

# Logs
docker logs vibe

# Restart
docker compose restart
```

---

## 📍 File Structure

```
vibe/
├── app/                    ← Backend (FastAPI)
├── android/                ← Android app
├── downloads/              ← Downloaded music
├── vibe-config.json        ← Configuration ✓
├── docker-compose.yml
├── Dockerfile
└── README.md
```

---

## 🎵 Download Formats

- MP3 (most compatible)
- M4A (iTunes quality)
- FLAC (lossless)
- Opus (modern compression)

---

## ✅ What's Enabled

- ✓ Spotify downloads
- ✓ YouTube downloads (with Deno)
- ✓ Batch processing
- ✓ Real-time logs
- ✓ Admin customization
- ✓ File management

---

## 🆘 Troubleshooting

**Can't connect?**
- Check: `docker ps | findstr vibe`
- Logs: `docker logs vibe`
- Port: Should be 8081

**Download failed?**
- Check internet
- Verify link is valid
- See logs for details

**YouTube not working?**
- Deno is enabled ✓
- Try different video
- Check privacy settings

---

**One folder. Everything included. Ready to use.** 🚀🎵
