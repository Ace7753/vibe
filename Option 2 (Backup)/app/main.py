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
    return config

SITE_CONFIG = load_config()
JOBS: Dict[str, dict] = {}

app = FastAPI(title="Vibe")
app.mount("/downloads", StaticFiles(directory=str(DOWNLOAD_DIR)), name="downloads")
app.mount("/archives", StaticFiles(directory=str(ARCHIVE_DIR)), name="archives")

# --- UI (Simplified for Mobile/Termux) ---
@app.get("/", response_class=HTMLResponse)
async def index():
    c = SITE_CONFIG
    return f"""
<!DOCTYPE html>
<html>
<head>
    <title>{c['title']}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{ background: {c['bg']}; color: white; font-family: sans-serif; padding: 20px; }}
        .btn {{ background: {c['accent']}; color: black; padding: 10px; border-radius: 5px; text-decoration: none; display: inline-block; }}
    </style>
</head>
<body>
    <h1>{c['title']}</h1>
    <p>{c['tagline']}</p>
    <div style="background: rgba(255,255,255,0.1); padding: 20px; border-radius: 10px;">
        <input type="text" id="q" placeholder="Spotify Link" style="width: 80%; padding: 10px;">
        <button onclick="dl()" class="btn">Download</button>
    </div>
    <div id="status">READY</div>
    <a id="pack" href="#" style="display:none;" class="btn">📦 Download Pack Your Files</a>
    <script>
        async function dl() {{
            const q = document.getElementById('q').value;
            document.getElementById('status').innerText = 'Starting...';
            const fd = new FormData(); fd.append('query', q);
            const res = await fetch('/api/download', {{method:'POST', body:fd}});
            const data = await res.json();
            poll(data.job_id);
        }}
        async function poll(id) {{
            const res = await fetch('/api/jobs/'+id);
            const job = await res.json();
            document.getElementById('status').innerText = job.status;
            if(job.status === 'complete') {{
                if(job.zip_url) {{
                    const p = document.getElementById('pack');
                    p.href = job.zip_url; p.style.display = 'block';
                }}
            }} else if(job.status !== 'failed') {{
                setTimeout(() => poll(id), 1000);
            }}
        }}
    </script>
</body>
</html>
"""

# API endpoints would follow... (simplified for brevity)
