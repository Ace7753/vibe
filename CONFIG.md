# ⚙️ Vibe Configuration

## Current Settings

```json
{
    "title": "Vibe",
    "tagline": "Spotify Downloader",
    "accent": "#ff2e88",
    "bg": "#050505",
    "port": 8081
}
```

---

## How to Change Configuration

### Option 1: Edit File (Restart Required)

Edit: `vibe/vibe-config.json`

```json
{
    "title": "Your App Name",
    "tagline": "Your tagline here",
    "accent": "#YOUR_COLOR",
    "bg": "#YOUR_BG_COLOR",
    "port": 8081
}
```

Then restart:
```bash
docker compose restart
```

### Option 2: Via Web Admin Panel (No Restart)

1. Go to: http://localhost:8081
2. Click settings icon (bottom right)
3. Edit title, tagline, colors
4. Click "Save"

---

## Color Codes

**Accent (Main Color):**
- Pink: `#ff2e88`
- Cyan: `#00d4ff`
- Purple: `#b833ff`
- Green: `#00ff88`

**Background (Dark Mode):**
- Deep Black: `#050505`
- Charcoal: `#0a0a0a`
- Dark Gray: `#1a1a1a`

---

## Configuration File Location

```
vibe/vibe-config.json
```

---

## Current Status

✓ Title: **Vibe**
✓ Tagline: **Spotify Downloader**
✓ Accent: **#ff2e88** (Pink)
✓ Background: **#050505** (Black)
✓ Port: **8081**

---

## What Each Setting Does

| Setting | What it controls |
|---------|-----------------|
| title | App name shown at top |
| tagline | Subtitle/description |
| accent | Pink color for buttons & highlights |
| bg | Dark background color |
| port | Server port (8081) |

---

**Configuration is live and active!** 🎨
