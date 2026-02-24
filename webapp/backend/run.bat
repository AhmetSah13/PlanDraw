@echo off
REM Backend'i venv ile calistirir (PowerShell script kısıtı yok).
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Venv yok, olusturuluyor...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

uvicorn app.main:app --reload --port 8000
pause
