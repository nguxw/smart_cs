@echo off
setlocal

cd /d "%~dp0"

set DATA_BACKEND=postgres
set REDIS_BACKEND=redis
set KB_BACKEND=qdrant
set DATABASE_URL=postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs
set REDIS_URL=redis://localhost:6379/0
set QDRANT_URL=http://localhost:6333

".conda\python.exe" -m uvicorn app.api.main:app --app-dir backend --host 127.0.0.1 --port 8000
