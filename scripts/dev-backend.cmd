@echo off
REM Backend (FastAPI/uvicorn) - repo root'tan çağrılır
cd /d "%~dp0..\webapp\backend"
if exist ".venv\Scripts\python.exe" (
    .venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
) else (
    python -m uvicorn app.main:app --reload --port 8000
)
