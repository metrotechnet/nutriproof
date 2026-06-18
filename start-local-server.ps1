param(
    [int]$Port = 8080
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Ensure commands run from repository root (where app.py lives).
Set-Location $PSScriptRoot

$pythonExe = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

if (Test-Path $pythonExe) {
    $pythonCommand = $pythonExe
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonCommand = "py"
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonCommand = "python"
} else {
    throw "Python introuvable. Creez d'abord l'environnement virtuel (.venv) et installez les dependances."
}

$env:PORT = "$Port"
Write-Host "Starting local server on http://localhost:$Port"

if ($pythonCommand -eq "py") {
    & py app.py
} else {
    & $pythonCommand app.py
}
