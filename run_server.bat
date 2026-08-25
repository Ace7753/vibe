@echo off
cd /d C:\Users\ljack\Documents\Codex\2026-06-26\al\vibe
python -m uvicorn app.main:app --host 0.0.0.0 --port 8080 > server_out.log 2>&1