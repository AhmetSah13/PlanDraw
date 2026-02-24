@echo off
REM Frontend (Vite) - repo root'tan çağrılır
cd /d "%~dp0..\webapp\frontend"
npm run dev
