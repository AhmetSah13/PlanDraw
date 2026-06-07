param(
    [Parameter(Mandatory = $true)]
    [string]$Sketch,

    [Parameter(Mandatory = $true)]
    [string]$Fqbn
)

$ErrorActionPreference = "Stop"

function Resolve-RepoRoot {
    $here = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $here "..")).Path
}

$repoRoot = Resolve-RepoRoot
$sketchPath = Join-Path $repoRoot $Sketch

if (-not (Test-Path $sketchPath)) {
    Write-Error "Sketch path not found: $sketchPath"
}

$ino = Get-ChildItem -Path $sketchPath -Filter "*.ino" -File | Select-Object -First 1
if (-not $ino) {
    Write-Error "No .ino file found under: $sketchPath"
}

$arduinoCli = Get-Command arduino-cli -ErrorAction SilentlyContinue
if (-not $arduinoCli) {
    Write-Error @"
arduino-cli not found in PATH.
Install arduino-cli and ensure it is available, then retry.
See firmware/BUILD.md for setup steps.
"@
}

if ([string]::IsNullOrWhiteSpace($Fqbn)) {
    Write-Error "Fqbn is required. Do not rely on a default board; set -Fqbn explicitly."
}

Write-Host "Repo root:" $repoRoot
Write-Host "Sketch:" $sketchPath
Write-Host "FQBN:" $Fqbn
Write-Host "Running: arduino-cli compile --fqbn $Fqbn $Sketch"

Push-Location $repoRoot
try {
    & arduino-cli compile --fqbn $Fqbn $Sketch
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
    Write-Host "Compile succeeded."
    exit 0
}
finally {
    Pop-Location
}
