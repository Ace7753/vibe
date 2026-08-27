import asyncio
import json
import os
import sys
import uuid
import zipfile
import socket
import shutil
from pathlib import Path
from typing import Dict

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

# --- PATHS ---
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", str(BASE_DIR / "downloads"))).resolve()
ARCHIVE_DIR = Path(os.getenv("ARCHIVE_DIR", str(BASE_DIR / "archives"))).resolve()
COOKIE_FILE = BASE_DIR / "cookies.txt"

for d in [DOWNLOAD_DIR, ARCHIVE_DIR]: d.mkdir(exist_ok=True)

SITE_CONFIG = {"title": "Vibe", "tagline": "Spotify Downloader", "accent": "#ff2e88", "bg": "#050505"}
JOBS: Dict[str, dict] = {}

app = FastAPI()
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")
app.mount("/assets", StaticFiles(directory=str(BASE_DIR)), name="assets")

# --- ENGINE CHAIN ---
async def try_engine(job, label, cmd, extra_env=None):
    job["log"].append(f"🔍 [Chain] Attempting Engine: {label}...")
    env = os.environ.copy()
    if extra_env: env.update(extra_env)
    # Ensure merger folders are in PYTHONPATH for this subprocess
    merger_path = "/app/engines/merger:/app/engines/merger/src:/app/engines/merger/savify:/app/engines/merger/votify"
    env["PYTHONPATH"] = f"{merger_path}:{env.get('PYTHONPATH', '')}"

    try:
        proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT, env=env)

        async def read_stream(stream):
            while True:
                line = await stream.readline()
                if not line: break
                msg = line.decode(errors='replace').strip()
                if msg:
                    job["log"].append(f"[{label}] {msg[:100]}")
                    job["log"] = job["log"][-100:]

        try:
            await asyncio.wait_for(read_stream(proc.stdout), timeout=420) # 7 min timeout
        except asyncio.TimeoutError:
            proc.kill()
            job["log"].append(f"⚠️ {label} timed out.")
            return False

        rc = await proc.wait()
        return rc == 0
    except Exception as e:
        job["log"].append(f"⚠️ {label} failed: {str(e)[:50]}")
        return False

async def run_vibe_engine(job_id: str, query: str, base_url: str):
    job = JOBS[job_id]
    job["status"] = "running"
    before = {f.name for f in DOWNLOAD_DIR.glob("*")}

    # --- THE ULTIMATE 10-ENGINE NUCLEAR CHAIN ---
    engines = [
        ("SpotDL", [sys.executable, "-m", "spotdl", "download", query, "--output", str(DOWNLOAD_DIR), "--format", "m4a", "--threads", "4", "--yt-dlp-args", "--impersonate chrome --no-check-certificate --extractor-args \"youtube:player_client=android,ios,web\""]),
        ("Spotify-DL", ["spotifydl", "--url", query, "--output", str(DOWNLOAD_DIR)]),
        ("Votify", [sys.executable, "-m", "votify", query, "-o", str(DOWNLOAD_DIR)]),
        ("OnTheSpot", [sys.executable, "-m", "onthespot", query]),
        ("Savify", [sys.executable, "-m", "savify", "download", query, "--path", str(DOWNLOAD_DIR)]),
        ("Antra", [sys.executable, "-m", "antra", query, "-o", str(DOWNLOAD_DIR)]),
        ("SpotiFLAC", ["go", "run", "/app/engines/merger/main.go", query]),
        ("EzYTDL", ["node", "/app/engines/merger/index.js", "--headless", query]),
        ("Web-Downloader", [sys.executable, "-m", "spotify_web_downloader", query, "-o", str(DOWNLOAD_DIR)]),
        ("Brute-Fallback", [sys.executable, "/app/engines/merger/spotify_to_mp3.py", query])
    ]

    for label, cmd in engines:
        if len({f.name for f in DOWNLOAD_DIR.glob("*")} - before) > 0:
            job["log"].append(f"✅ Track snagged by {label}!")
            break

        if COOKIE_FILE.exists():
            if label in ["SpotDL", "Votify", "Web-Downloader"]:
                cmd.extend(["--cookie-file" if label=="SpotDL" else "-c", str(COOKIE_FILE)])

        await try_engine(job, label, cmd)

    after = {f.name for f in DOWNLOAD_DIR.glob("*")}
    new_files = list(after - before)
    if new_files:
        job["status"] = "complete"
        zip_name = f"Vibe_Pack_{job_id[:4]}.zip"
        with zipfile.ZipFile(ARCHIVE_DIR / zip_name, 'w') as zf:
            for f in new_files: zf.write(DOWNLOAD_DIR / f, arcname=f)
        job["zip_url"] = f"{base_url}/archives/{zip_name}"
    else:
        job["status"] = "failed"
        job["log"].append("❌ CRITICAL: ALL 10 ENGINES BLOCKED. Check your cookies.")

@app.post("/api/download")
async def start_dl(request: Request, query: str = Form(...)):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"id": job_id, "status": "queued", "log": ["Engine starting (Super-Chain)..."], "zip_url": None}
    asyncio.create_task(run_vibe_engine(job_id, query, str(request.base_url).rstrip('/')))
    return {"job_id": job_id}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str): return JOBS.get(job_id, {"status": "not_found", "log": []})

@app.get("/api/files")
async def list_files(request: Request):
    base_url = str(request.base_url).rstrip('/')
    files = [{"name": p.name, "url": f"{base_url}/archives/{p.name}", "type": "zip"} for p in sorted(ARCHIVE_DIR.glob("*.zip"), key=lambda x: x.stat().st_mtime, reverse=True)]
    files += [{"name": p.name, "url": f"{base_url}/downloads/{p.name}", "type": "mp3"} for p in sorted(DOWNLOAD_DIR.glob("*"), key=lambda x: x.stat().st_mtime, reverse=True) if p.is_file()]
    return {"files": files[:150]}

@app.post("/api/save_cookies")
async def save_cookies(data: dict):
    cookies = data.get("cookies", "")
    if cookies: COOKIE_FILE.write_text(cookies); return {"status": "ok"}
    return {"status": "error"}

@app.post("/api/clear")
async def clear_downloads():
    for folder in [DOWNLOAD_DIR, ARCHIVE_DIR]:
        for item in folder.glob("*"):
            if item.is_file(): item.unlink()
    return {"status": "ok"}

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
        .nav-active {{ color: {c['accent']}; opacity: 1 !important; }}
    </style>
</head>
<body class="min-h-screen pb-24">
    <div class="fixed inset-0 pointer-events-none z-0"><div class="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] rounded-full opacity-20 blur-[120px]" style="background: {c['accent']};"></div></div>
    <nav class="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 glass rounded-full px-6 py-3 flex gap-8 shadow-2xl">
        <button onclick="showPage('download')" id="nav-download" class="nav-active opacity-60"><svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg></button>
        <button onclick="showPage('files')" id="nav-files" class="opacity-60"><svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M9 12h6m-6 4h6m2 5H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5.586a1 1 0 0 1 .707.293l5.414 5.414a1 1 0 0 1 .293.707V19a2 2 0 0 1-2 2z"/></svg></button>
        <button onclick="showPage('settings')" id="nav-settings" class="opacity-60"><svg class="w-6 h-6" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24"><path d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z"/><path d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg></button>
    </nav>
    <main class="relative z-10 max-w-xl mx-auto pt-16 px-6">
        <header class="mb-12 flex justify-between items-start">
            <div class="flex items-center gap-4"><img src="/assets/vibe_icon_original.png" class="w-12 h-12 rounded-xl shadow-xl"><div><h1 class="text-3xl font-black tracking-tighter">Vibe</h1><p class="text-xs font-bold opacity-40 uppercase">Ultimate Chain v4</p></div></div>
            <button onclick="clearAll()" class="text-[10px] font-black opacity-30 hover:opacity-100 uppercase transition-all">Clear All</button>
        </header>
        <section id="page-download" class="space-y-8">
            <h2 class="text-5xl font-black italic tracking-tighter">Download <span style="color:#ff2e88">Spotify</span></h2>
            <div class="glass rounded-2xl p-2 flex items-center shadow-2xl"><input type="text" id="query" placeholder="Paste link..." class="bg-transparent flex-1 px-6 py-4 outline-none text-lg font-bold"><button onclick="dl()" class="w-14 h-14 rounded-2xl flex items-center justify-center text-black shadow-xl font-black" style="background:#ff2e88;">GO</button></div>
            <div id="card" class="glass rounded-2xl p-8 space-y-4">
                <div class="flex justify-between items-center"><span class="text-[10px] opacity-40 uppercase font-black tracking-widest">Chain Status</span><span id="st" class="text-xs px-3 py-1 rounded bg-neutral-900 text-cyan-400 font-bold">READY</span></div>
                <div class="w-full bg-white/5 rounded-full h-1 overflow-hidden"><div id="bar" class="h-full transition-all duration-1000 rounded-full" style="width: 0%; background: #ff2e88"></div></div>
                <div id="logs" class="text-[9px] font-mono text-emerald-500/50 h-32 overflow-y-auto leading-tight p-4 bg-black/20 rounded-xl border border-white/5">Waiting for task...</div>
                <a id="zip" href="#" class="hidden w-full block bg-white/5 text-center py-4 rounded-xl font-bold text-cyan-400 border border-white/10 shadow-xl">📦 Download Pack</a>
            </div>
        </section>
        <section id="page-files" class="hidden space-y-6"><h2 class="text-5xl font-black italic tracking-tighter">Your <span style="color:#ff2e88">Files</span></h2><div id="fl" class="space-y-3"></div></section>
        <section id="page-settings" class="hidden space-y-6"><h2 class="text-5xl font-black italic tracking-tighter text-center">Settings</h2><div class="glass rounded-2xl p-8 space-y-4"><h3 class="text-xs uppercase font-black opacity-40">Cookie Manager</h3><textarea id="cookies" class="w-full h-48 bg-black/40 rounded-xl p-4 font-mono text-[10px] outline-none border border-white/10" placeholder="Paste cookies..."></textarea><button onclick="save()" class="w-full py-4 rounded-xl font-bold text-black" style="background:#ff2e88;">SAVE VAULT</button></div></section>
    </main>
    <script>
        let cur = null;
        function showPage(p) {{ ['download','files', 'settings'].forEach(id => {{ document.getElementById('page-'+id).classList.add('hidden'); document.getElementById('nav-'+id).classList.remove('nav-active'); }}); document.getElementById('page-'+p).classList.remove('hidden'); document.getElementById('nav-'+p).classList.add('nav-active'); if(p==='files') rf(); }}
        async function dl() {{ const q = document.getElementById('query').value.trim(); if(!q) return; document.getElementById('bar').style.width = '10%'; document.getElementById('logs').innerText = 'Initializing Nuclear Chain...'; const fd = new FormData(); fd.append('query', q); const res = await fetch('/api/download', {{method:'POST', body:fd}}); const d = await res.json(); cur = d.job_id; poll(); }}
        async function poll() {{
            if(!cur) return;
            const res = await fetch('/api/jobs/'+cur);
            const j = await res.json();
            document.getElementById('st').innerText = j.status;
            document.getElementById('logs').innerText = j.log.join('\\n');
            document.getElementById('logs').scrollTop = 9999;
            if(j.status==='running'||j.status==='queued') {{ document.getElementById('bar').style.width = '50%'; setTimeout(poll, 1500); }}
            else {{
                if (j.status === 'complete') document.getElementById('bar').style.width = '100%';
                if(j.zip_url) {{const z=document.getElementById('zip'); z.href=j.zip_url; z.classList.remove('hidden');}}
                rf();
            }}
        }}
        async function rf() {{ const res = await fetch('/api/files'); const d = await res.json(); document.getElementById('fl').innerHTML = d.files.length ? d.files.map(f => `<a href="${{f.url}}" download class="glass flex items-center gap-4 p-4 rounded-xl"><div class="text-2xl">${{f.type==='zip'?'📦':'🎵'}}</div><div class="flex-1 min-w-0"><p class="truncate text-sm font-bold">${{f.name}}</p></div></a>`).join('') : '<p class="opacity-20 text-center font-bold">Empty</p>'; }}
        async function save() {{ const c = document.getElementById('cookies').value; await fetch('/api/save_cookies', {{method:'POST', headers:{{'Content-Type':'application/json'}}, body: JSON.stringify({{cookies:c}})}}); alert('Vault Saved!'); }}
        async function clearAll() {{ if(confirm('Clear all?')) {{ await fetch('/api/clear', {{method:'POST'}}); rf(); }} }}
        showPage('download');
    </script>
</body>
</html>
    """

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
