# spotDL + YouTube Music App

A Dockerized web app that follows the Gordon setup: Spotify links or spotDL search text go through spotDL, and spotDL uses YouTube Music as the audio provider.

Use this only for content you own or are authorized to download.

## What It Does

- Accepts Spotify track, album, playlist, and artist URLs
- Accepts search text like `Artist - Song`
- Uses `spotdl download --audio youtube-music` behind the scenes
- Installs spotDL from the upstream repository during Docker build
- Installs `yt-dlp` and `ffmpeg` in the container
- Saves spotDL config/cache in `./config`
- Saves music in `./downloads` unless `MUSIC_DIR` is set

## Run

```powershell
docker compose up --build
```

Then open:

```text
http://localhost:8080
```

## Auto ZIP Download

When a download job finishes, the app creates one ZIP containing the new songs from that job and automatically starts the browser download. If the browser blocks the automatic download, use the `Download ZIP` link that appears above the job log.

The original files also stay in the mounted music folder.

## Output Structure

Playlists:

```text
Playlists/Playlist Name/1. Artist - Title.mp3
```

Albums:

```text
Artist - Album/01. Title.mp3
```

Single tracks and search results:

```text
Artist - Title.mp3
```

## Music Folder

Copy `.env.example` to `.env` and edit `MUSIC_DIR` to download into a custom folder.

## CLI Use

```powershell
docker compose run --rm spotdl-app spotdl --version
```

```powershell
docker compose run --rm spotdl-app spotdl download --audio youtube-music "https://open.spotify.com/album/ALBUM_ID"
```

## Pin spotDL

By default, Docker builds from the latest upstream repository state. To pin a branch, tag, or commit, edit `.env`:

```env
SPOTDL_REF=v4.2.11
```
