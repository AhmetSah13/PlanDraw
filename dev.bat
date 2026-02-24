@echo off
REM Tek komut: Backend + Frontend ayni anda (tek terminal, tek Ctrl+C)
cd /d "%~dp0"
if not exist "node_modules\concurrently" (
  echo concurrently yok, npm install calistiriliyor...
  call npm install
)
npm run dev
