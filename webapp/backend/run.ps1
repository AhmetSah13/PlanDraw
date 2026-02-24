# PowerShell'de ExecutionPolicy hatasi verirse venv aktif olmadan calistirmak icin:
# Proje kokunden: .\webapp\backend\run.ps1
# veya webapp/backend icinden: .\run.ps1

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$backend = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"

if (-not (Test-Path $venvPython)) {
    Write-Host "Venv yok, olusturuluyor..."
    Set-Location $backend
    & python -m venv .venv
    & $venvPython -m pip install -r requirements.txt
}

Set-Location $backend
& $venvPython -m uvicorn app.main:app --reload --port 8000
