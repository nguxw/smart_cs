@echo off
setlocal

cd /d "%~dp0"

set DATABASE_URL=postgresql+psycopg://smartcs:smartcs@localhost:5432/smartcs
set QDRANT_URL=http://localhost:6333
set QDRANT_COLLECTION=smartcs_kb

".conda\python.exe" scripts\seed_demo_data.py
