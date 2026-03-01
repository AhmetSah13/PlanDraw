# Backend'i yeni modüler yapidan calistirir (backend/).
# Proje kokunden: .\webapp\backend\run.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backendDir = Join-Path $root "backend"

if (-not (Test-Path $backendDir)) {
    Write-Error "backend klasoru bulunamadi: $backendDir"
}

Set-Location $backendDir
$venvPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    & $venvPython -m uvicorn app.api.main:app --reload --port 8000
} else {
    python -m uvicorn app.api.main:app --reload --port 8000
}
