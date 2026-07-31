# Vibe Environment Variables

Use these variables to configure your server when hosting in the cloud (Render, Railway, etc.).

## 🎨 UI Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `VIBE_TITLE` | The title of your downloader | `Vibe` |
| `VIBE_TAGLINE` | The subtitle/tagline | `Spotify Downloader` |
| `VIBE_ACCENT` | Accent color (Hex code) | `#ff2e88` |
| `VIBE_BG` | Background color (Hex code) | `#050505` |

## ⚙️ System Configuration
| Variable | Description | Default |
|----------|-------------|---------|
| `PORT` | The port the server runs on | `8080` |
| `DOWNLOAD_DIR` | Where tracks are saved | `./downloads` |
| `ARCHIVE_DIR` | Where ZIP packs are saved | `./archives` |

## 🎵 Spotify API (Optional)
*Setting these can improve metadata accuracy and prevent rate limiting.*
| Variable | Description |
|----------|-------------|
| `SPOTIPY_CLIENT_ID` | Your Spotify Client ID |
| `SPOTIPY_CLIENT_SECRET` | Your Spotify Client Secret |

---

### How to set on Render:
1. Go to your **Dashboard**.
2. Select your **Vibe Web Service**.
3. Go to **Environment**.
4. Click **Add Environment Variable**.
5. Enter the Key and Value from the tables above.
6. Click **Save Changes**.
