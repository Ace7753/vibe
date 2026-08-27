import asyncio
import mimetypes
import os
import re
import shlex
import socket
import sys
import threading
import uuid
import uvicorn
import webbrowser
import zipfile
import spotdl
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
ARCHIVE_DIR = BASE_DIR / "archives"
YOUTUBE_MUSIC_AUDIO = "youtube-music"

for folder in (DOWNLOAD_DIR, ARCHIVE_DIR):
    folder.mkdir(parents=True, exist_ok=True)

SPOTIFY_URL_RE = re.compile(
    r"^https://open\.spotify\.com/(track|album|playlist|artist)/[A-Za-z0-9]+"
)

JOBS: Dict[str, dict] = {}

app = FastAPI(title="Spotify To MP3")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def append_log(job_id: str, message: str) -> None:
    job = JOBS[job_id]
    job["log"].append(message)
    job["log"] = job["log"][-300:]


def validate_input(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(400, "Enter a Spotify URL or search query.")
    if SPOTIFY_URL_RE.match(cleaned):
        return cleaned
    if "://" not in cleaned and 2 <= len(cleaned) <= 300:
        return cleaned
    raise HTTPException(400, "Use a Spotify URL or a search like Artist - Song.")


def smart_template(query: str) -> str:
    q = query.lower()
    if "open.spotify.com/playlist" in q:
        return "Playlists/{artist} - {title}.{output-ext}"
    if "open.spotify.com/album" in q:
        return "{artist} - {album}/{track-number}. {title}.{output-ext}"
    if "open.spotify.com/artist" in q:
        return "Artists/{artist}/{album}/{track-number}. {title}.{output-ext}"
    return "{artist} - {title}.{output-ext}"


def resolve_output(query: str) -> str:
    pattern = smart_template(query)
    if "{output-ext}" not in pattern:
        pattern += ".{output-ext}"
    return str(DOWNLOAD_DIR / pattern.replace("\\", "/").strip())


def all_files() -> List[Path]:
    return [p for p in DOWNLOAD_DIR.rglob("*") if p.is_file() and p.name != ".gitkeep"]


def all_items() -> List[Path]:
    items = list(all_files())
    items.extend(ARCHIVE_DIR.glob("*.zip"))
    return items


def file_list() -> List[dict]:
    files = []
    for path in sorted(all_files(), key=lambda p: p.stat().st_mtime, reverse=True):
        rel = path.relative_to(DOWNLOAD_DIR).as_posix()
        files.append(
            {
                "name": rel,
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "url": f"/downloads/{rel}",
            }
        )
    for path in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        files.append(
            {
                "name": path.name,
                "size": path.stat().st_size,
                "modified": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
                "url": f"/archives/{path.name}",
            }
        )
    return files[:200]


def latest_file() -> Optional[Path]:
    items = sorted(all_items(), key=lambda p: p.stat().st_mtime, reverse=True)
    return items[0] if items else None


def make_archive(job_id: str, files: List[str]) -> dict:
    archive_path = ARCHIVE_DIR / f"spotdl-{job_id}.zip"
    count = 0
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for rel in files:
            src = (DOWNLOAD_DIR / rel).resolve()
            try:
                src.relative_to(DOWNLOAD_DIR)
            except ValueError:
                continue
            if src.is_file():
                zf.write(src, arcname=rel)
                count += 1
    if count == 0:
        archive_path.unlink(missing_ok=True)
        return {"ready": False, "file_count": 0}
    return {"ready": True, "file_count": count, "name": archive_path.name, "url": f"/api/jobs/{job_id}/archive"}


async def run_download(job_id: str, query: str, fmt: str, quality: str, output: str) -> None:
    job = JOBS[job_id]
    job["status"] = "running"
    job["started_at"] = utc_now()

    cmd = [
        sys.executable, "-m", "spotdl",
        "download", query,
        "--audio", YOUTUBE_MUSIC_AUDIO,
        "--output", output,
        "--format", fmt,
        "--bitrate", quality,
        "--overwrite", "skip",
    ]
    job["command"] = shlex.join(cmd)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
    except FileNotFoundError:
        job["status"] = "failed"
        job["finished_at"] = utc_now()
        append_log(job_id, "ERROR: spotdl not found.")
        return

    assert proc.stdout
    async for line in proc.stdout:
        append_log(job_id, line.decode(errors="replace").rstrip())

    rc = await proc.wait()
    job["finished_at"] = utc_now()
    job["return_code"] = rc

    if rc == 0:
        before = set(job.get("before_files", []))
        new_files = sorted({f.relative_to(DOWNLOAD_DIR).as_posix() for f in all_files()} - before)
        if new_files:
            job["archive"] = await asyncio.to_thread(make_archive, job_id, new_files)
            append_log(job_id, f"Done — {job['archive']['file_count']} new file(s).")
        else:
            job["archive"] = {"ready": False, "file_count": 0}
            append_log(job_id, "Done — no new files were created.")
        job["status"] = "complete"
    else:
        job["archive"] = {"ready": False, "file_count": 0}
        job["status"] = "failed"


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Spotify To MP3</title>
<style>
body { margin: 0; min-height: 100vh; background: #0b1220; color: #e5e7eb; font-family: system-ui, sans-serif; }
.container { max-width: 980px; margin: auto; padding: 24px; }
.card { background: #111827; border: 1px solid #1f2937; border-radius: 18px; padding: 24px; }
h1 { margin: 0 0 12px; }
p { margin: 0 0 24px; color: #94a3b8; }
label { display: block; margin-bottom: 12px; color: #cbd5e1; }
input, select, button { width: 100%; box-sizing: border-box; }
input, select { margin-top: 8px; padding: 12px 14px; border-radius: 12px; border: 1px solid #334155; background: #0f172a; color: #e5e7eb; }
button { margin-top: 16px; padding: 12px 14px; border-radius: 12px; border: none; background: #38bdf8; color: #0f172a; cursor: pointer; }
.button-small { width: auto; padding: 10px 12px; font-size: 0.95rem; }
.grid { display: grid; gap: 18px; }
.row { display: grid; gap: 16px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
pre { margin: 0; padding: 16px; border-radius: 14px; background: #0f172a; border: 1px solid #334155; max-height: 260px; overflow: auto; white-space: pre-wrap; }
.file-link { display: block; margin-bottom: 10px; padding: 12px; border-radius: 12px; background: #0f172a; border: 1px solid #334155; color: #e5e7eb; text-decoration: none; }
.status { margin-top: 12px; color: #e2e8f0; }
@media (max-width: 720px) { .row { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<div class="container">
  <div class="card">
    <h1>Spotify To MP3</h1>
    <p>Paste a Spotify URL or search phrase and download audio.</p>

    <form id="download-form">
      <label>Spotify URL or Search
        <input id="query" name="query" required placeholder="https://open.spotify.com/album/... or Artist - Song">
      </label>

      <div class="row">
        <label>Format
          <select id="format" name="format">
            <option value="mp3">MP3</option>
            <option value="m4a">M4A</option>
            <option value="opus">Opus</option>
            <option value="flac">FLAC</option>
          </select>
        </label>

        <label>Bitrate
          <select id="quality" name="quality">
            <option value="128k">128k</option>
            <option value="192k">192k</option>
            <option value="256k">256k</option>
            <option value="320k" selected>320k</option>
          </select>
        </label>
      </div>

      <button type="submit">Start Download</button>
    </form>

    <div class="status" id="status-text">Ready.</div>

    <h2>Job Log</h2>
    <pre id="log-pre">No job started yet.</pre>

    <div style="display:flex; gap:12px; flex-wrap:wrap; margin-top:18px;">
      <button id="refresh-btn" class="button-small">Refresh files</button>
      <button id="clear-history-btn" class="button-small">Clear downloads</button>
      <button id="latest-btn" class="button-small">Latest file</button>
    </div>

    <h2 style="margin-top:24px;">Downloaded Files</h2>
    <div id="files-list">Loading...</div>
  </div>
</div>

<script>
const logPre = document.getElementById("log-pre");
const statusText = document.getElementById("status-text");
const filesList = document.getElementById("files-list");
const form = document.getElementById("download-form");
const refreshBtn = document.getElementById("refresh-btn");
const clearBtn = document.getElementById("clear-history-btn");
const latestBtn = document.getElementById("latest-btn");
let activeJob = null;

function setStatus(text) { statusText.textContent = text; }
function log(text) { logPre.textContent += text + "\\n"; logPre.scrollTop = logPre.scrollHeight; }

async function refreshFiles() {
  const res = await fetch("/api/files");
  if (!res.ok) return;
  const data = await res.json();
  filesList.innerHTML = "";
  if (!data.files.length) {
    filesList.textContent = "No downloads yet.";
    return;
  }
  data.files.forEach(file => {
    const a = document.createElement("a");
    a.href = file.url;
    a.target = "_blank";
    a.className = "file-link";
    a.textContent = `${file.name} (${file.size} bytes)`;
    filesList.appendChild(a);
  });
}

async function pollJob() {
  if (!activeJob) return;
  const res = await fetch(`/api/jobs/${activeJob}`);
  if (!res.ok) return;
  const job = await res.json();
  setStatus(`Job ${job.status}`);
  if (job.log && job.log.length) job.log.forEach(line => log(line));
  if (job.status === "queued" || job.status === "running") {
    setTimeout(pollJob, 2000);
  } else {
    activeJob = null;
    refreshFiles();
  }
}

form.addEventListener("submit", async event => {
  event.preventDefault();
  logPre.textContent = "";
  setStatus("Starting download...");
  const res = await fetch("/api/download", {
    method: "POST",
    body: new FormData(form),
  });
  const body = await res.json();
  if (!res.ok) {
    setStatus("Error");
    log(body.detail || "Unable to start download.");
    return;
  }
  activeJob = body.job_id;
  setStatus("Queued");
  log(`Job started: ${activeJob}`);
  pollJob();
});

refreshBtn.addEventListener("click", refreshFiles);

clearBtn.addEventListener("click", async () => {
  if (!confirm("Delete all downloaded files?")) return;
  setStatus("Clearing downloads...");
  const res = await fetch("/api/files/clear", { method: "POST" });
  if (!res.ok) {
    setStatus("Error clearing downloads.");
    return;
  }
  setStatus("Download history cleared.");
  refreshFiles();
});

latestBtn.addEventListener("click", async () => {
  const res = await fetch("/api/files/latest");
  if (!res.ok) {
    setStatus("No latest file available.");
    return;
  }
  const data = await res.json();
  window.open(data.url, "_blank");
});

refreshFiles();
</script>
</body>
</html>
"""


@app.post("/api/download")
async def start_download(
    query: str = Form(...),
    audio_format: str = Form("mp3", alias="format"),
    quality: str = Form("320k"),
) -> JSONResponse:
    allowed_formats = {"mp3", "m4a", "opus", "flac"}
    allowed_qualities = {"128k", "192k", "256k", "320k"}

    target = validate_input(query)
    if audio_format not in allowed_formats:
        raise HTTPException(400, "Unsupported audio format.")
    if quality not in allowed_qualities:
        raise HTTPException(400, "Unsupported bitrate.")

    output = resolve_output(target)
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {
        "id": job_id,
        "status": "queued",
        "query": target,
        "before_files": sorted({f.relative_to(DOWNLOAD_DIR).as_posix() for f in all_files()}),
        "archive": {"ready": False, "file_count": 0},
        "log": [],
        "created_at": utc_now(),
    }
    asyncio.create_task(run_download(job_id, target, audio_format, quality, output))
    return JSONResponse({"job_id": job_id})


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str) -> JSONResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    return JSONResponse({k: v for k, v in job.items() if k != "before_files"})


@app.get("/api/jobs/{job_id}/archive")
async def download_archive(job_id: str) -> FileResponse:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found.")
    arc = job.get("archive") or {}
    path = ARCHIVE_DIR / f"spotdl-{job_id}.zip"
    if not arc.get("ready") or not path.is_file():
        raise HTTPException(404, "Archive not ready.")
    return FileResponse(path, media_type="application/zip", filename=arc.get("name", path.name))


@app.get("/api/files")
async def get_files() -> JSONResponse:
    return JSONResponse({"files": file_list()})


@app.post("/api/files/clear")
async def clear_files() -> JSONResponse:
    for f in all_files():
        f.unlink(missing_ok=True)
    for folder in sorted(DOWNLOAD_DIR.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if folder.is_dir():
            try:
                folder.rmdir()
            except OSError:
                pass
    for z in ARCHIVE_DIR.glob("*.zip"):
        z.unlink(missing_ok=True)
    return JSONResponse({"status": "ok"})


@app.get("/api/files/latest")
async def get_latest_file() -> JSONResponse:
    file = latest_file()
    if not file:
        raise HTTPException(404, "No downloaded files found.")
    if file.parent == ARCHIVE_DIR:
        url = f"/archives/{file.name}"
    else:
        url = f"/downloads/{file.relative_to(DOWNLOAD_DIR).as_posix()}"
    return JSONResponse(
        {
            "name": file.name,
            "url": url,
            "size": file.stat().st_size,
            "modified": datetime.fromtimestamp(file.stat().st_mtime, timezone.utc).isoformat(),
        }
    )


@app.get("/download/latest")
async def download_latest() -> FileResponse:
    file = latest_file()
    if not file:
        raise HTTPException(404, "No downloaded files found.")
    media_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
    return FileResponse(file, media_type=media_type, filename=file.name)


def is_port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def find_free_port(preferred_ports=(8080, 8085, 8086, 8090, 0)) -> int:
    for port in preferred_ports:
        if port == 0:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.bind(("127.0.0.1", 0))
                return sock.getsockname()[1]
        if not is_port_busy(port):
            return port
    raise RuntimeError("No free port available.")


def main() -> None:
    port = 0
    env_port = os.getenv("PORT", "").strip()
    if env_port.isdigit():
        port = int(env_port)
        if is_port_busy(port):
            print(f"Port {port} is busy, selecting a free port automatically.")
            port = find_free_port()
    else:
        port = find_free_port()

    url = f"http://127.0.0.1:{port}"
    print(f"Starting Spotify To MP3 app at {url}")
    threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    main()
