# Vibe Environment Variables

Use these variables to configure your server when hosting in the cloud (AWS, Render, Railway, etc.).

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

### How to set on AWS (App Runner / ECS):
1. Go to your **AWS Console**.
2. Select your **Vibe Service**.
3. Go to **Configuration** or **Environment Variables**.
4. Add the Key and Value from the tables above.
5. Apply changes.
