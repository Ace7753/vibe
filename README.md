# 🎵 Vibe (Local & Cloud)

[![Status](https://img.shields.io/badge/Status-Local_Active-success?style=for-the-badge&logo=android)](http://127.0.0.1:8080/)
[![Platform](https://img.shields.io/badge/Platform-Android-blue?style=for-the-badge&logo=android)](https://github.com/Ace7753/vibeandroid)

**The powerful music downloader for Android, optimized for local Termux & AWS Cloud.**
This branch contains the Android app configured for **Local Mode** by default. It connects to your local Vibe engine (Termux or PC) at `http://127.0.0.1:8080/`.

---

## 🚀 Quick Start

### 1️⃣ Install the Vibe App
Install the [**vibe.apk**](vibe.apk) found in the root of this project onto your phone.

### 2️⃣ Start your Server
- **Termux:** Run `python app/main.py`
- **PC:** Run `run_server.bat`
- The app will connect to `http://127.0.0.1:8080/` automatically.

### 3️⃣ Switch to Cloud (Optional)
1. **Long-press** anywhere on the screen.
2. Enter the AWS URL: `http://vibe-alb-1651997055.us-east-1.elb.amazonaws.com/`
3. Tap **Connect**.

---

## ⚡ Features

- ✅ **Cloud-Powered**: Downloads are processed by your remote server, saving your phone's battery.
- ✅ **Metadata & Lyrics**: Automatically fetches high-quality art and synced lyrics.
- ✅ **Remote Access**: Works from anywhere with an internet connection. No PC required.
- ✅ **Secure Switcher**: Long-press gesture to swap between different cloud servers or local engines.

---

## 📂 Project Structure

```text
vibe/
├── android/        # Android Studio project (The Client)
├── app/            # Vibe Engine (Cloud/Server source)
├── vibe.apk        # The installable app
└── README.md       # You are here!
```

---

## 📱 Other Versions

Looking for the **100% Standalone (Offline)** version?  
Switch to the [**`option-2`**](https://github.com/Ace7753/vibeandroid/tree/option-2) branch to see instructions for running the engine directly on your phone via Termux.

**Stay connected. Stay Vibe-ing.** 🎵☁️✨
