import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
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

    # Environment Variable Overrides (Cloud-Friendly)
    env_map = {
        "VIBE_TITLE": "title",
        "VIBE_TAGLINE": "tagline",
        "VIBE_ACCENT": "accent",
        "VIBE_BG": "bg"
    }
    for env_key, config_key in env_map.items():
        val = os.getenv(env_key)
        if val: config[config_key] = val

    return config

SITE_CONFIG = load_config()
JOBS: Dict[str, dict] = {}
MASTER_TOKEN = "MASTER_ADMIN_UNLOCKED"

app = FastAPI(title="Vibe")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")

# --- ENGINE ---
async def run_spotdl(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}
    cmd = [sys.executable, "-m", "spotdl", "download", query, "--output", str(DOWNLOAD_DIR / "{artist} - {title}.{output-ext}")]
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        assert proc.stdout
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
                zip_name = f"Vibe_{job_id[:8]}.zip"
                with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
                    for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
                job["zip_url"] = f"{base_url}/archives/{zip_name}"
    except Exception as e:
        job["status"] = "failed"; job["log"].append(f"Error: {str(e)}")

# --- API ---
@app.get("/api/health")
async def health(): 
    return {"status": "ok"}

@app.get("/api/config_data")
async def get_cfg(): 
    return SITE_CONFIG

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    base_url = str(request.base_url).rstrip('/')
    JOBS[job_id] = {"id": job_id, "query": query, "status": "queued", "log": ["Engine starting..."], "zip_url": None}
    asyncio.create_task(run_spotdl(job_id, query, base_url))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): 
    return JOBS.get(job_id, {"status": "not_found", "log": []})

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

@app.post("/api/config")
async def update_config(token: str = Form(...), title: str = Form(...), tagline: str = Form(...), accent: str = Form(...), bg: str = Form(...)):
    if token != MASTER_TOKEN: raise HTTPException(401)
    SITE_CONFIG.update({"title": title, "tagline": tagline, "accent": accent, "bg": bg})
    CONFIG_FILE.write_text(json.dumps(SITE_CONFIG, indent=4))
    return {"status": "ok"}

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
    </nav>
    <main class="relative z-10 max-w-xl mx-auto pt-16 px-6 pb-32">
        <header class="mb-12">
            <h1 id="vibe-logo" class="text-3xl font-black tracking-tighter">{c['title']}</h1>
            <p class="text-xs font-bold opacity-40">{c['tagline']}</p>
        </header>
        <section id="page-download" class="tab-transition space-y-8">
            <h2 class="text-5xl font-black">Download <span style="color:{c['accent']}">Spotify</span></h2>
            <div class="glass rounded-2xl p-2 flex items-center shadow-2xl">
                <input type="text" id="dl-query" placeholder="Paste Spotify link..." class="bg-transparent flex-1 px-6 py-4 outline-none text-lg font-bold">
                <button onclick="startDownload()" class="w-14 h-14 rounded-2xl flex items-center justify-center text-black shadow-xl" style="background:{c['accent']};"><svg class="w-6 h-6 fill-none stroke-current stroke-3" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></button>
            </div>
            <div id="status-card" class="glass rounded-2xl p-8">
                <div class="flex justify-between mb-4"><span class="text-xs opacity-40">Engine</span><span id="engine-status" class="text-xs px-3 py-1 rounded bg-neutral-900 text-cyan-400">READY</span></div>
                <div id="engine-log" class="text-xs font-mono text-emerald-500/80 h-32 overflow-y-auto leading-relaxed p-1">> Ready</div>
                <a id="insta-zip" href="#" class="hidden mt-4 w-full block bg-cyan-500/10 text-center py-3 rounded-xl font-bold text-cyan-400 border border-cyan-500/20">📦 Download Pack</a>
            </div>
        </section>
        <section id="page-files" class="hidden tab-transition space-y-6">
            <h2 class="text-5xl font-black">Your <span style="color:{c['accent']}">Files</span></h2>
            <div id="file-list" class="space-y-3"></div>
        </section>
    </main>
    <script>
        let currentJob = null;
        function showPage(p) {{ ['download','files'].forEach(id => {{ document.getElementById('page-'+id).classList.add('hidden'); document.getElementById('nav-'+id).classList.remove('nav-active'); }}); document.getElementById('page-'+p).classList.remove('hidden'); document.getElementById('nav-'+p).classList.add('nav-active'); if(p==='files') refreshFiles(); }}
        async function startDownload() {{ const q = document.getElementById('dl-query').value.trim(); if(!q) return; const fd = new FormData(); fd.append('query', q); const res = await fetch('/api/download', {{method:'POST', body:fd}}); const data = await res.json(); currentJob = data.job_id; pollEngine(); }}
        async function pollEngine() {{ if(!currentJob) return; const res = await fetch('/api/jobs/'+currentJob); const job = await res.json(); document.getElementById('engine-status').innerText = job.status; document.getElementById('engine-log').innerText = job.log.join('\\n'); const log = document.getElementById('engine-log'); log.scrollTop = log.scrollHeight; if(job.status==='running'||job.status==='queued') {{setTimeout(pollEngine, 1000);}} else {{ if(job.zip_url) {{const z=document.getElementById('insta-zip'); z.href=job.zip_url; z.classList.remove('hidden');}} refreshFiles(); }} }}
        async function refreshFiles() {{ const res = await fetch('/api/files'); const data = await res.json(); document.getElementById('file-list').innerHTML = data.files.map(f => `<a href="${{f.url}}" download class="glass flex items-center gap-4 p-4 rounded-xl"><div class="text-2xl">${{f.type==='zip'?'📦':'🎵'}}</div><div class="flex-1 min-w-0"><p class="truncate text-sm font-bold">${{f.name}}</p><p class="text-xs opacity-50">${{(f.size/1024/1024).toFixed(1)}}MB</p></div></a>`).join(''); }}
        showPage('download');
    </script>
</body>
</html>
    """

# --- UTILS ---
def is_port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0

if __name__ == "__main__":
    port = int(os.getenv("PORT", SITE_CONFIG.get("port", 8080)))
    while is_port_busy(port):
        if os.getenv("PORT"): break # Don't loop in cloud environments
        port += 1
    print(f"Vibe running on http://localhost:{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
