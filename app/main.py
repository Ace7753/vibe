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

app = FastAPI(title="Vibe")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR)), name="assets")

# --- MULTI-ENGINE CHAIN ---
async def try_engine(job, name, cmd, extra_env=None):
    job["log"].append(f"🔍 [Engine] Swapping to {name}...")
    env = os.environ.copy()
    if extra_env: env.update(extra_env)
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            msg = line.decode(errors='replace').strip()
            if msg:
                job["log"].append(f"[{name}] {msg[:100]}")
                job["log"] = job["log"][-100:]
        rc = await proc.wait()
        return rc == 0
    except Exception as e:
        job["log"].append(f"⚠️ {name} skip: {str(e)[:50]}")
        return False

async def run_vibe_engine(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}

    # --- ENGINE 1: SPOTDL (MASTER) ---
    spotdl_cmd = [
        sys.executable, "-m", "spotdl", "download", query,
        "--output", str(DOWNLOAD_DIR), "--format", "m4a", "--threads", "4",
        "--audio", "youtube-music", "youtube", "soundcloud",
        "--yt-dlp-args", "--no-check-certificate --geo-bypass --rm-cache-dir --extractor-args \"youtube:player_client=ios,web;player_skip=webpage\""
    ]
    if COOKIE_FILE.exists(): spotdl_cmd.extend(["--cookie-file", str(COOKIE_FILE)])
    await try_engine(job, "SpotDL", spotdl_cmd)

    # --- ENGINE 2: SPOTIFY-DL (NODE) ---
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "Spotify-DL", ["spotifydl", "--url", query, "--output", str(DOWNLOAD_DIR)])

    # --- ENGINE 3: VOTIFY ---
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        # Protobuf fix for Votify
        await try_engine(job, "Votify", ["votify", query, "-o", str(DOWNLOAD_DIR)], {"PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION": "python"})

    # --- ENGINE 4: ONTHESPOT ---
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "OnTheSpot", ["onthespot-cli", query])

    # FINAL ASSEMBLY
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    new_files = list(after - before)
    if new_files:
        job["status"] = "complete"
        zip_name = f"Vibe_Pack_{job_id[:4]}.zip"
        with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
            for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
        job["zip_url"] = f"{base_url}/archives/{zip_name}"
        job["log"].append("✅ Track secured! Download ready.")
    else:
        job["status"] = "failed"
        job["log"].append("❌ Every GitHub engine failed. Check your cookies or query.")

# --- API ---
@app.get("/api/health")
async def health(): return {"status": "ok"}

@app.get("/api/config_data")
async def get_cfg(): return SITE_CONFIG

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    base_url = str(request.base_url).rstrip('/')
    JOBS[job_id] = {"id": job_id, "query": query, "status": "queued", "log": ["Engine starting (Multi-Fallback)..."], "zip_url": None}
    asyncio.create_task(run_vibe_engine(job_id, query, base_url))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.get("/api/files")
async def list_files(request: Request):
    base_url = str(request.base_url).rstrip('/')
    files = []
    for p in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True):
        files.append({"name": p.name, "url": f"{base_url}/archives/{p.name}", "type": "zip"})
    for p in sorted(DOWNLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.is_file() and not p.name.startswith('.'):
            files.append({"name": p.name, "url": f"{base_url}/downloads/{p.name}", "type": "mp3"})
    return {"files": files[:150]}

@app.post("/api/save_cookies")
async def save_cookies(data: dict):
    cookies = data.get("cookies", "")
    if cookies:
        COOKIE_FILE.write_text(cookies)
        return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/clear")
async def clear_downloads():
    for folder in [DOWNLOAD_DIR, ARCHIVE_DIR]:
        for item in folder.glob("*"):
            if item.is_file(): item.unlink()
    return {"status": "ok"}

# --- UI (ORIGINAL PINK VIBE RESTORED) ---
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
    </style>
</head>
<body class="min-h-screen pb-24">
    <div class="fixed inset-0 pointer-events-none z-0">
        <div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full opacity-20 blur-[120px]" style="background: {c['accent']};"></div>
    </div>

    <nav class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 glass rounded-full px-6 py-3 flex gap-8 items-center shadow-2xl">
        <button onclick="showPage('download')" id="nav-download" class="nav-active opacity-60 hover:opacity-100">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
        </button>
        <button onclick="showPage('files')" id="nav-files" class="opacity-60 hover:opacity-100">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/></svg>
        </button>
        <button onclick="showPage('settings')" id="nav-settings" class="opacity-60 hover:opacity-100">
            <svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
        </button>
    </nav>

    <main class="relative z-10 max-w-xl mx-auto pt-16 px-6 pb-32">
        <header class="mb-12 flex justify-between items-start">
            <div class="flex items-center gap-4">
                <img src="/assets/vibe_icon_original.png" class="w-12 h-12 rounded-xl shadow-xl" alt="Logo">
                <div>
                    <h1 class="text-3xl font-black tracking-tighter">{c['title']}</h1>
                    <p class="text-xs font-bold opacity-40">{c['tagline']}</p>
                </div>
            </div>
            <div class="flex gap-2">
                 <button onclick="clearAll()" class="text-[10px] font-black opacity-30 hover:opacity-100 border border-white/20 px-3 py-1 rounded-full uppercase tracking-tighter transition-all">Clear All</button>
            </div>
        </header>

        <section id="page-download" class="space-y-8">
            <h2 class="text-5xl font-black italic tracking-tighter">Download <span style="color:{c['accent']}">Spotify</span></h2>
            <div class="glass rounded-2xl p-2 flex items-center shadow-2xl">
                <input type="text" id="dl-query" placeholder="Paste Spotify link..." class="bg-transparent flex-1 px-6 py-4 outline-none text-lg font-bold">
                <button onclick="startDownload()" class="w-14 h-14 rounded-2xl flex items-center justify-center text-black shadow-xl accent-bg font-black">GO</button>
            </div>
            <div id="status-card" class="glass rounded-2xl p-8 space-y-6">
                <div class="flex justify-between mb-4"><span class="text-xs opacity-40 uppercase tracking-widest font-bold">Progress</span><span id="engine-status" class="text-xs px-3 py-1 rounded bg-neutral-900 text-cyan-400 font-bold">READY</span></div>
                <div class="space-y-4">
                    <p id="activity-text" class="text-sm font-bold opacity-80 truncate">Waiting for input...</p>
                    <div class="w-full bg-white/5 rounded-full h-1 overflow-hidden">
                        <div id="progress-bar" class="h-full transition-all duration-500 rounded-full" style="width: 0%; background: {c['accent']}"></div>
                    </div>
                </div>
                <button onclick="toggleLogs()" class="mt-6 text-[10px] opacity-30 hover:opacity-100 uppercase font-black tracking-tighter transition-all">View Technical Details</button>
                <div id="engine-log-container" class="hidden mt-4">
                    <div id="engine-log" class="text-[9px] font-mono text-emerald-500/50 h-48 overflow-y-auto leading-tight p-4 bg-black/20 rounded-xl border border-white/5">Ready</div>
                </div>
                <a id="insta-zip" href="#" class="hidden w-full block bg-white/5 text-center py-4 rounded-xl font-bold text-cyan-400 border border-white/10 shadow-xl">📦 Download Pack Your Files</a>
            </div>
        </section>

        <section id="page-files" class="hidden space-y-6">
            <h2 class="text-5xl font-black italic tracking-tighter">Your <span style="color:{c['accent']}">Files</span></h2>
            <div id="file-list" class="space-y-3"></div>
        </section>

        <section id="page-settings" class="hidden space-y-6">
            <h2 class="text-5xl font-black italic tracking-tighter text-center">Settings</h2>
            <div class="glass rounded-2xl p-8 space-y-4">
                <h3 class="text-xs uppercase font-black opacity-40">Cookie Manager</h3>
                <textarea id="cookie-input" class="w-full h-48 bg-black/40 rounded-xl p-4 font-mono text-[10px] outline-none border border-white/10" placeholder="Paste cookies.txt content here..."></textarea>
                <button onclick="saveCookies()" class="w-full py-4 rounded-xl font-bold accent-bg text-black uppercase">Save Cookies</button>
            </div>
        </section>
    </main>

    <script>
        let currentJob = null;
        function toggleLogs() {{ const log = document.getElementById('engine-log-container'); log.classList.toggle('hidden'); }}
        function showPage(p) {{ ['download','files', 'settings'].forEach(id => {{ document.getElementById('page-'+id).classList.add('hidden'); document.getElementById('nav-'+id).classList.remove('nav-active'); }}); document.getElementById('page-'+p).classList.remove('hidden'); document.getElementById('nav-'+p).classList.add('nav-active'); if(p==='files') refreshFiles(); }}
        async function startDownload() {{ const q = document.getElementById('dl-query').value.trim(); if(!q) return; document.getElementById('progress-bar').style.width = '10%'; document.getElementById('activity-text').innerText = 'Initializing...'; const fd = new FormData(); fd.append('query', q); const res = await fetch('/api/download', {{method:'POST', body:fd}}); const data = await res.json(); currentJob = data.job_id; pollEngine(); }}
        async function pollEngine() {{
            if(!currentJob) return;
            const res = await fetch('/api/jobs/'+currentJob);
            const job = await res.json();
            document.getElementById('engine-status').innerText = job.status;
            const logElement = document.getElementById('engine-log');
            logElement.innerText = job.log.join('\\n');
            logElement.scrollTop = logElement.scrollHeight;
            if(job.status==='running'||job.status==='queued') {{ document.getElementById('progress-bar').style.width = '50%'; setTimeout(pollEngine, 1500); }}
            else {{
                if (job.status === 'complete') {{ document.getElementById('progress-bar').style.width = '100%'; document.getElementById('activity-text').innerText = 'Complete!'; }}
                if(job.zip_url) {{const z=document.getElementById('insta-zip'); z.href=job.zip_url; z.classList.remove('hidden');}}
                refreshFiles();
            }}
        }}
        async function refreshFiles() {{ const res = await fetch('/api/files'); const data = await res.json(); document.getElementById('file-list').innerHTML = data.files.length ? data.files.map(f => `<a href="${{f.url}}" download class="glass flex items-center gap-4 p-4 rounded-xl"><div class="text-2xl">${{f.type==='zip'?'📦':'🎵'}}</div><div class="flex-1 min-w-0"><p class="truncate text-sm font-bold">${{f.name}}</p></div></a>`).join('') : '<p class="text-center py-12 opacity-20 font-bold">No files yet</p>'; }}
        async function saveCookies() {{ const cookies = document.getElementById('cookie-input').value; await fetch('/api/save_cookies', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{cookies}})}}); alert('Cookies Saved!'); }}
        async function clearAll() {{ if(confirm('Clear all downloads?')) {{ await fetch('/api/clear', {{method:'POST'}}); refreshFiles(); }} }}
        showPage('download');
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
