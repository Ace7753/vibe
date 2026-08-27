import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Set

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", str(BASE_DIR / "archives"))).resolve()
CONFIG_FILE = BASE_DIR / "vibe-config.json"
COOKIE_FILE = BASE_DIR / "cookies.txt"

for d in [DOWNLOAD_DIR, ARCHIVE_DIR]: d.mkdir(exist_ok=True)

# --- CONFIG ---
DEFAULT_CONFIG = {
    "title": "Vibe",
    "tagline": "Spotify Downloader",
    "accent": "#ff2e88",
    "bg": "#050505",
    "port": 8080
}

def load_config():
    config = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try: config.update(json.loads(CONFIG_FILE.read_text()))
        except: pass
    return config

SITE_CONFIG = load_config()
JOBS: Dict[str, dict] = {}
MASTER_TOKEN = "MASTER_ADMIN_UNLOCKED"

app = FastAPI(title="Vibe")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR)), name="assets")

# --- ENGINE ---
async def get_metadata(query: str):
    temp_meta = BASE_DIR / f"meta_{uuid.uuid4().hex}.spotdl"
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "spotdl", "save", query,
            "--save-file", str(temp_meta),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        if temp_meta.exists():
            data = json.loads(temp_meta.read_text())
            if isinstance(data, list) and len(data) > 0:
                first = data[0]
                artist = first.get("artist", "Unknown")
                album = first.get("album_name", "Unknown")
                name = first.get("name", "Unknown")
                if "/playlist/" in query: return "Playlist"
                if len(data) > 1: return f"{artist} - {album}"
                return f"{artist} - {name}"
    except: pass
    finally:
        if temp_meta.exists(): temp_meta.unlink()
    return "Vibe_Pack"

async def run_spotdl(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    zip_base_name = await get_metadata(query)
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}
    is_playlist = "/playlist/" in query
    output_template = "{list-position} - {artist} - {title}.{output-ext}" if is_playlist else "{artist} - {title}.{output-ext}"

    # --- THE AWS NUCLEAR BYPASS (AUGUST 2026) ---
    # 1. We prioritize YouTube Music/YouTube now that cookies are confirmed working
    # 2. Relaxed duration matching (max-duration-error) to fix "No usable results"
    # 3. Explicitly enabling Deno for cloud IP decryption
    cmd = [
        sys.executable, "-m", "spotdl", "download", query,
        "--output", str(DOWNLOAD_DIR / output_template),
        "--format", "m4a",
        "--bitrate", "disable",
        "--threads", "4",
        "--max-duration-error", "120",
        "--use-deno",
        "--search-query", "{artist} - {title}",
        "--audio", "youtube-music", "youtube", "soundcloud", "piped",
        "--yt-dlp-args", "--no-check-certificate --geo-bypass --rm-cache-dir --extractor-args \"youtube:player_client=ios,web;player_skip=webpage\" --add-header \"Accept-Language:en-US,en;q=0.9\" --add-header \"Referer:https://www.google.com/\""
    ]

    if is_playlist: cmd.append("--playlist-numbering")

    # Check environment variable first, then file
    vibe_cookies_env = os.getenv("VIBE_COOKIES")
    if vibe_cookies_env:
        COOKIE_FILE.write_text(vibe_cookies_env)
        job["log"].append("🎫 Cookies injected from VIBE_COOKIES environment.")

    if COOKIE_FILE.exists():
        cmd.extend(["--cookie-file", str(COOKIE_FILE)])
        job["log"].append(f"🎫 Cookies applied ({COOKIE_FILE.stat().st_size} bytes)")
    else:
        job["log"].append("⚠️ No cookies found. AWS may be blocked. Use Settings to add them!")

    env = os.environ.copy()
    env["SPOTDL_CACHE_DIR"] = str(BASE_DIR)

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            msg = line.decode(errors='replace').strip()
            if msg: job["log"].append(msg); job["log"] = job["log"][-100:]
        rc = await proc.wait()
        job["status"] = "complete" if rc == 0 else "failed"
        if rc == 0:
            after = {f.name for f in DOWNLOAD_DIR.glob("*")}
            new_files = list(after - before)
            if new_files:
                safe_name = "".join([c for c in zip_base_name if c.isalnum() or c in (' ', '-', '_')]).strip()
                zip_name = f"{safe_name}_{job_id[:4]}.zip"
                with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
                    for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
                job["zip_url"] = f"{base_url}/archives/{zip_name}"
    except Exception as e:
        job["status"] = "failed"; job["log"].append(f"Error: {str(e)}")

# --- API ---
@app.get("/api/health")
async def health(): return {"status": "ok"}

@app.get("/api/config_data")
async def get_cfg(): return SITE_CONFIG

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    base_url = str(request.base_url).rstrip('/')
    JOBS[job_id] = {"id": job_id, "query": query, "status": "queued", "log": ["Engine starting (iOS Bypass)..."], "zip_url": None}
    asyncio.create_task(run_spotdl(job_id, query, base_url))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.get("/api/files")
async def list_files(request: Request):
    base_url = str(request.base_url).rstrip('/')
    files = []
    for p in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({"name": p.name, "url": f"{base_url}/archives/{p.name}", "type": "zip", "size": p.stat().st_size})
    for p in sorted(DOWNLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and not p.name.startswith('.'):
            files.append({"name": p.name, "url": f"{base_url}/downloads/{p.name}", "type": "mp3", "size": p.stat().st_size})
    return {"files": files[:150]}

@app.post("/api/clear")
async def clear_downloads():
    for folder in [DOWNLOAD_DIR, ARCHIVE_DIR]:
        for item in folder.glob("*"):
            if item.is_file(): item.unlink()
    return {"status": "ok"}

@app.post("/api/save_cookies")
async def save_cookies(data: dict):
    cookies = data.get("cookies", "")
    if cookies:
        COOKIE_FILE.write_text(cookies)
        return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/fix_engine")
async def fix_engine():
    # Clear yt-dlp cache on server
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "spotdl", "--clear-cache",
            stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL
        )
        await proc.wait()
        return {"status": "ok"}
    except: return {"status": "error"}

# --- UI ---
@app.get("/", response_class=HTMLResponse)
async def index():
    c = SITE_CONFIG
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>{c['title']}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {{ font-family: 'Plus Jakarta Sans', sans-serif; background-color: {c['bg']}; color: #f5f5f5; overflow-x: hidden; }}
        .glass {{ background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }}
        .accent-bg {{ background: {c['accent']}; }}
        .nav-active {{ color: {c['accent']}; opacity: 1 !important; }}
        .tab-transition {{ transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1); }}
    </style>
</head>
<body class="min-h-screen pb-24">
    <div class="fixed inset-0 pointer-events-none z-0">
        <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full opacity-20 blur-[120px]" style="background: {c['accent']};"></div>
    </div>

    <nav class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 glass rounded-full px-6 py-3 flex gap-8 items-center shadow-2xl">
        <button onclick="showPage('download')" id="nav-download" class="nav-active opacity-60 hover:opacity-100 tab-transition">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
        </button>
        <button onclick="showPage('files')" id="nav-files" class="opacity-60 hover:opacity-100 tab-transition">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/></svg>
        </button>
        <button onclick="showPage('settings')" id="nav-settings" class="opacity-60 hover:opacity-100 tab-transition">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        </button>
    </nav>

    <main class="relative z-10 max-w-xl mx-auto pt-16 px-6 pb-32">
        <header class="mb-12 flex justify-between items-start">
            <div class="flex items-center gap-4">
                <img src="/assets/vibe_icon_original.png" class="w-12 h-12 rounded-xl shadow-xl" alt="Logo">
                <div>
                    <h1 id="vibe-logo" class="text-3xl font-black tracking-tighter">{c['title']}</h1>
                    <p class="text-xs font-bold opacity-40">{c['tagline']}</p>
                </div>
            </div>
            <div class="flex gap-2">
                 <button onclick="fixEngine()" class="text-[10px] font-black bg-cyan-500/10 text-cyan-400 border border-cyan-500/20 px-3 py-1 rounded-full uppercase tracking-tighter transition-all">Fix Engine</button>
                 <button onclick="clearAll()" class="text-[10px] font-black opacity-30 hover:opacity-100 border border-white/20 px-3 py-1 rounded-full uppercase tracking-tighter transition-all">Clear All</button>
            </div>
        </header>

        <section id="page-download" class="tab-transition space-y-8">
            <h2 class="text-5xl font-black">Download <span style="color:{c['accent']}">Spotify</span></h2>
            <div class="glass rounded-2xl p-2 flex items-center shadow-2xl">
                <input type="text" id="dl-query" placeholder="Paste Spotify link..." class="bg-transparent flex-1 px-6 py-4 outline-none text-lg font-bold">
                <button onclick="startDownload()" class="w-14 h-14 rounded-2xl flex items-center justify-center text-black shadow-xl" style="background:{c['accent']};"><svg class="w-6 h-6 fill-none stroke-current stroke-3" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></button>
            </div>
            <div id="status-card" class="glass rounded-2xl p-8">
                <div class="flex justify-between mb-4"><span class="text-xs opacity-40 uppercase tracking-widest font-bold">Progress</span><span id="engine-status" class="text-xs px-3 py-1 rounded bg-neutral-900 text-cyan-400 font-bold">READY</span></div>
                <div class="space-y-4">
                    <p id="activity-text" class="text-sm font-bold opacity-80 truncate">Waiting for input...</p>
                    <div class="w-full bg-white/5 rounded-full h-2 overflow-hidden">
                        <div id="progress-bar" class="h-full transition-all duration-500 rounded-full" style="width: 0%; background: {c['accent']}"></div>
                    </div>
                </div>
                <button onclick="toggleLogs()" class="mt-6 text-[10px] opacity-30 hover:opacity-100 uppercase font-black tracking-tighter transition-all">View Technical Details</button>
                <div id="engine-log-container" class="hidden mt-4">
                    <div id="engine-log" class="text-[10px] font-mono text-emerald-500/60 h-32 overflow-y-auto leading-tight p-2 bg-black/20 rounded-lg">Ready</div>
                </div>
                <a id="insta-zip" href="#" class="hidden mt-4 w-full block bg-cyan-500/10 text-center py-3 rounded-xl font-bold text-cyan-400 border border-cyan-500/20">📦 Download Pack Your Files</a>
            </div>
        </section>

        <section id="page-files" class="hidden tab-transition space-y-6">
            <h2 class="text-5xl font-black">Your <span style="color:{c['accent']}">Files</span></h2>
            <div id="file-list" class="space-y-3"></div>
        </section>

        <section id="page-settings" class="hidden tab-transition space-y-6">
            <h2 class="text-5xl font-black">Settings</h2>
            <div class="glass rounded-2xl p-8 space-y-4">
                <h3 class="text-xs uppercase font-black opacity-40">Cookie Manager</h3>
                <p class="text-xs opacity-60">If downloads fail with "Sign in to confirm you're not a bot", paste your cookies.txt text here.</p>
                <textarea id="cookie-input" class="w-full h-48 bg-black/40 rounded-xl p-4 font-mono text-[10px] outline-none border border-white/10" placeholder="Paste cookies.txt content here..."></textarea>
                <button onclick="saveCookies()" class="w-full py-3 rounded-xl font-bold accent-bg text-black">Save Cookies</button>
            </div>
        </section>
    </main>

    <script>
        let currentJob = null;
        function toggleLogs() {{ const log = document.getElementById('engine-log-container'); log.classList.toggle('hidden'); }}
        function showPage(p) {{ ['download','files', 'settings'].forEach(id => {{ document.getElementById('page-'+id).classList.add('hidden'); document.getElementById('nav-'+id).classList.remove('nav-active'); }}); document.getElementById('page-'+p).classList.remove('hidden'); document.getElementById('nav-'+p).classList.add('nav-active'); if(p==='files') refreshFiles(); }}
        async function startDownload() {{ const q = document.getElementById('dl-query').value.trim(); if(!q) return; document.getElementById('progress-bar').style.width = '5%'; document.getElementById('activity-text').innerText = 'Initializing...'; const fd = new FormData(); fd.append('query', q); const res = await fetch('/api/download', {{method:'POST', body:fd}}); const data = await res.json(); currentJob = data.job_id; pollEngine(); }}
        async function clearAll() {{ if(!confirm('Clear all downloads and archives?')) return; await fetch('/api/clear', {{method:'POST'}}); refreshFiles(); alert('Cleared!'); }}
        async function saveCookies() {{ const cookies = document.getElementById('cookie-input').value; await fetch('/api/save_cookies', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{cookies}})}}); alert('Cookies Saved!'); }}
        async function fixEngine() {{ await fetch('/api/fix_engine', {{method:'POST'}}); alert('Engine cache cleared and refreshed!'); }}

        async function pollEngine() {{
            if(!currentJob) return;
            const res = await fetch('/api/jobs/'+currentJob);
            const job = await res.json();
            document.getElementById('engine-status').innerText = job.status;
            const logElement = document.getElementById('engine-log');
            logElement.innerText = job.log.join('\\n');
            logElement.scrollTop = logElement.scrollHeight;
            const lastLines = job.log.slice(-10);
            let progress = 0;
            let activity = "Processing...";
            for (const line of lastLines) {{
                const pctMatch = line.match(/(\\d+(\\.\\d+)?%)/);
                if (pctMatch) progress = parseFloat(pctMatch[1]);
                if (line.includes('Downloading')) {{
                    const songMatch = line.match(/Downloading\\s+(.*)/);
                    if (songMatch) activity = songMatch[1];
                }}
                if (line.includes('Searching')) activity = 'Searching for best match...';
                if (line.includes('Converting')) activity = 'Optimizing audio...';
            }}
            if (progress > 0) document.getElementById('progress-bar').style.width = progress + '%';
            document.getElementById('activity-text').innerText = activity;
            if(job.status==='running'||job.status==='queued') {{
                setTimeout(pollEngine, 1000);
            }} else {{
                if (job.status === 'complete') document.getElementById('progress-bar').style.width = '100%';
                if(job.zip_url) {{const z=document.getElementById('insta-zip'); z.href=job.zip_url; z.classList.remove('hidden');}}
                refreshFiles();
            }}
        }}
        async function refreshFiles() {{ const res = await fetch('/api/files'); const data = await res.json(); document.getElementById('file-list').innerHTML = data.files.length ? data.files.map(f => `<a href="${{f.url}}" download class="glass flex items-center gap-4 p-4 rounded-xl"><div class="text-2xl">${{f.type==='zip'?'📦':'🎵'}}</div><div class="flex-1 min-w-0"><p class="truncate text-sm font-bold">${{f.name}}</p><p class="text-xs opacity-50">${{(f.size/1024/1024).toFixed(1)}}MB</p></div></a>`).join('') : '<p class="text-center py-12 opacity-20 font-bold">No files yet</p>'; }}
        showPage('download');
    </script>
</body>
</html>
    """

# --- UTILS ---
def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def is_port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0

if __name__ == "__main__":
    port = int(os.getenv("PORT", SITE_CONFIG.get("port", 8080)))
    while is_port_busy(port):
        if os.getenv("PORT"): break
        port += 1

    local_ip = get_local_ip()
    print("\n" + "="*40)
    print("VIBE ENGINE STARTING")
    print(f"Localhost: http://localhost:{port}")
    print(f"Mobile:    http://{local_ip}:{port}")
    print("="*40 + "\n")

    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
