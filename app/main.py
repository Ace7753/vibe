import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
import shutil
from pathlib import Path
from typing import Dict, List

import uvicorn
from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", str(BASE_DIR / "archives"))).resolve()
COOKIE_FILE = BASE_DIR / "cookies.txt"

for d in [DOWNLOAD_DIR, ARCHIVE_DIR]: d.mkdir(exist_ok=True)

# --- CONFIG ---
SITE_CONFIG = {
    "title": "Vibe Infinity",
    "tagline": "The Ultimate GitHub Mega-Merge",
    "accent": "#ff2e88",
    "bg": "#020202"
}

JOBS: Dict[str, dict] = {}

app = FastAPI()
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR)), name="assets")

# --- THE INFINITY FALLBACK CHAIN ---
async def try_engine(job, name, cmd):
    job["log"].append(f"🔍 [CHAIN] Attempting Engine: {name}...")
    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
        while True:
            line = await proc.stdout.readline()
            if not line: break
            msg = line.decode(errors='replace').strip()
            if msg: job["log"].append(f"[{name}] {msg[:100]}"); job["log"] = job["log"][-100:]
        rc = await proc.wait()
        return rc == 0
    except Exception as e:
        job["log"].append(f"⚠️ {name} failed to launch: {e}")
        return False

async def run_infinity_engine(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}

    # 1. SPOTDL (The Master)
    spotdl_cmd = [sys.executable, "-m", "spotdl", "download", query, "--output", str(DOWNLOAD_DIR), "--threads", "4"]
    if COOKIE_FILE.exists(): spotdl_cmd.extend(["--cookie-file", str(COOKIE_FILE)])
    if await try_engine(job, "SpotDL", spotdl_cmd): pass

    # 2. SPOTIFY-DL (Node.js Fallback)
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "Spotify-DL", ["spotify-dl", "--url", query, "--output", str(DOWNLOAD_DIR)])

    # 3. VOTIFY (Python Fallback)
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "Votify", [sys.executable, "-m", "votify", query, "-o", str(DOWNLOAD_DIR)])

    # 4. SAVIFY
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "Savify", [sys.executable, "-m", "savify", query, "-o", str(DOWNLOAD_DIR)])

    # 5. ONTHESPOT
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    if len(after - before) == 0:
        await try_engine(job, "OnTheSpot", [sys.executable, "-m", "onthespot", query])

    # CHECK FINAL SUCCESS
    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    new_files = list(after - before)

    if new_files:
        job["status"] = "complete"
        zip_name = f"Infinity_Pack_{job_id[:4]}.zip"
        with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
            for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
        job["zip_url"] = f"{base_url}/archives/{zip_name}"
        job["log"].append("✅ SUCCESS: Tracks secured by Infinity Chain!")
    else:
        job["status"] = "failed"
        job["log"].append("❌ CRITICAL: Every engine on GitHub was blocked. Update your cookies!")

# --- API ---
@app.get("/api/health")
async def health(): return {"status": "ok"}

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"id": job_id, "status": "queued", "log": ["Infinity Loop Initializing..."], "zip_url": None}
    asyncio.create_task(run_infinity_engine(job_id, query, str(request.base_url).rstrip('/')))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.get("/api/files")
async def list_files(request: Request):
    base_url = str(request.base_url).rstrip('/')
    files = [{"name": p.name, "url": f"{base_url}/archives/{p.name}"} for p in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)]
    return {"files": files[:100]}

@app.post("/api/save_cookies")
async def save_cookies(data: dict):
    cookies = data.get("cookies", "")
    if cookies:
        COOKIE_FILE.write_text(cookies)
        return {"status": "ok"}
    return {"status": "error"}

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
    <style>
        body {{ background-color: {c['bg']}; color: #fff; font-family: sans-serif; }}
        .glass {{ background: rgba(255, 255, 255, 0.05); backdrop-filter: blur(20px); border: 1px solid rgba(255,255,255,0.1); }}
    </style>
</head>
<body class="min-h-screen p-6">
    <div class="max-w-xl mx-auto space-y-12 pt-12">
        <header class="text-center">
            <h1 class="text-6xl font-black italic tracking-tighter" style="color: {c['accent']}">INFINITY</h1>
            <p class="text-xs font-bold opacity-30 uppercase tracking-[0.5em]">Vibe Multi-Engine Merge</p>
        </header>

        <div class="glass rounded-3xl p-2 flex">
            <input type="text" id="query" placeholder="Spotify Link..." class="bg-transparent flex-1 p-6 outline-none font-bold text-xl">
            <button onclick="dl()" class="px-10 rounded-2xl font-black text-black" style="background: {c['accent']}">GO</button>
        </div>

        <div id="status" class="glass rounded-3xl p-8 space-y-4">
            <div class="flex justify-between text-[10px] font-black opacity-40 uppercase tracking-widest">
                <span>Chain Status</span>
                <span id="st-text">Idle</span>
            </div>
            <div class="w-full bg-white/5 h-1 rounded-full overflow-hidden">
                <div id="bar" class="h-full transition-all duration-1000" style="width:0%; background:{c['accent']}"></div>
            </div>
            <div id="logs" class="text-[9px] font-mono opacity-40 h-48 overflow-y-auto leading-relaxed">Awaiting input...</div>
            <a id="zip" href="#" class="hidden block w-full text-center py-4 rounded-2xl bg-white/10 font-bold text-cyan-400 border border-cyan-500/20">📦 DOWNLOAD INFINITY PACK</a>
        </div>
    </div>

    <script>
        let cur = null;
        async function dl() {{
            const q = document.getElementById('query').value;
            const fd = new FormData(); fd.append('query', q);
            const res = await fetch('/api/download', {{method:'POST', body:fd}});
            const d = await res.json(); cur = d.job_id;
            document.getElementById('zip').classList.add('hidden');
            poll();
        }}
        async function poll() {{
            if(!cur) return;
            const res = await fetch('/api/jobs/'+cur);
            const j = await res.json();
            document.getElementById('st-text').innerText = j.status;
            document.getElementById('logs').innerText = j.log.join('\\n');
            document.getElementById('logs').scrollTop = 9999;
            if(j.status === 'running') {{ document.getElementById('bar').style.width = '50%'; setTimeout(poll, 1000); }}
            else if(j.status === 'complete') {{
                document.getElementById('bar').style.width = '100%';
                if(j.zip_url) {{ const z=document.getElementById('zip'); z.href=j.zip_url; z.classList.remove('hidden'); }}
            }}
        }}
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
