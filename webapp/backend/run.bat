@echo off
REM UYARI: webapp/backend LEGACY/DEPRECATED. Source of truth: backend/
REM Bu script, yanlislikla legacy backend’i calistirmayi engellemek icin
REM sizi repo kokundeki backend/ uygulamasina yonlendirir.

setlocal
cd /d "%~dp0"

echo.
echo [UYARI] Bu klasor legacy: %cd%
echo [BILGI] Dogru backend: ..\..\backend  (uvicorn app.api.main:app)
echo.

REM Repo root = webapp\backend’in iki ust dizini
cd /d "..\.."
if not exist "backend\app\api\main.py" (
    echo [HATA] backend\app\api\main.py bulunamadi. Beklenen repo yapisi degismis olabilir.
    echo        Lutfen repo kokunden calistirin: npm run dev
    pause
    exit /b 1
)

cd /d "backend"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -m uvicorn app.api.main:app --reload --port 8000
) else (
    python -m uvicorn app.api.main:app --reload --port 8000
)
pause
