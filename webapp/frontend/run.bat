@echo off
REM Frontend Vite dev server (PowerShell script kisiti yok - CMD npm.cmd kullanir)
cd /d "%~dp0"

if not exist "node_modules" (
    echo node_modules yok, npm install calistiriliyor...
    npm.cmd install
)

npm.cmd run dev
pause
