param(
    [string]$OutputDir = (Join-Path $PSScriptRoot "dist")
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$projectRoot = $PSScriptRoot
$packageName = "NutriProof-mac-local"
$stageRoot = Join-Path $OutputDir $packageName
$zipPath = Join-Path $OutputDir "$packageName.zip"

Write-Host "=== Building macOS local-run ZIP ==="
Write-Host "Project root: $projectRoot"
Write-Host "Output dir:   $OutputDir"

if (Test-Path $stageRoot) {
    Remove-Item -Recurse -Force $stageRoot
}
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

function Copy-RequiredPath {
    param([string]$RelativePath)
    $src = Join-Path $projectRoot $RelativePath
    $dst = Join-Path $stageRoot $RelativePath
    if (-not (Test-Path $src)) {
        throw "Required path not found: $RelativePath"
    }
    $dstParent = Split-Path -Parent $dst
    if ($dstParent) {
        New-Item -ItemType Directory -Force -Path $dstParent | Out-Null
    }
    Copy-Item -Recurse -Force $src $dst
}

Copy-RequiredPath "app.py"
Copy-RequiredPath "requirements.txt"
Copy-RequiredPath "api"
Copy-RequiredPath "dbase"
Copy-RequiredPath "static"
Copy-RequiredPath "templates"
Copy-RequiredPath ".env.example"

# Remove Python cache artifacts from the package.
Get-ChildItem -Path $stageRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue |
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $stageRoot -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue |
    Remove-Item -Force -ErrorAction SilentlyContinue

$startCommand = @'
#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Python 3 is required and Homebrew is not installed."
    echo "Install Homebrew first: https://brew.sh"
    exit 1
  fi
  echo "Python 3 not found. Installing with Homebrew..."
  brew install python
fi

if ! command -v tesseract >/dev/null 2>&1; then
  if ! command -v brew >/dev/null 2>&1; then
    echo "Tesseract is required and Homebrew is not installed."
    echo "Install Homebrew first: https://brew.sh"
    exit 1
  fi
  echo "Tesseract not found. Installing with Homebrew..."
  brew install tesseract tesseract-lang
fi

if command -v brew >/dev/null 2>&1; then
  if ! brew list --formula tesseract-lang >/dev/null 2>&1; then
    echo "Installing tesseract language data..."
    brew install tesseract-lang
  fi
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if [ -f ".env" ]; then
  set -a
  . ./.env
  set +a
fi

export UPLOAD_ROOT="${UPLOAD_ROOT:-$HOME/NutriProof/uploads}"
export PORT="${PORT:-8080}"
mkdir -p "$UPLOAD_ROOT"

echo "Starting NutriProof server..."
echo "URL: http://localhost:$PORT/main"
echo "Data folder: $UPLOAD_ROOT"

python app.py
'@

$launcherPath = Join-Path $stageRoot "start.command"
[System.IO.File]::WriteAllText($launcherPath, $startCommand, [System.Text.UTF8Encoding]::new($false))

$readme = @'
NutriProof - Local web app package for macOS (unsigned)
========================================================

Requirements:
- macOS
- Homebrew (for automatic installation of Python and OCR dependencies)
- Internet access on first run (to install dependencies)

How to run:
1) Double-click "start.command"
2) If macOS blocks it, allow it from:
   System Settings -> Privacy & Security -> Open Anyway
3) Open your browser at:
   http://localhost:8080/main

Optional configuration:
- Copy .env.example to .env and edit values
- Default upload folder: ~/NutriProof/uploads
'@

$readmePath = Join-Path $stageRoot "README_MAC_LOCAL.txt"
[System.IO.File]::WriteAllText($readmePath, $readme, [System.Text.UTF8Encoding]::new($false))

if (Test-Path $zipPath) {
    Remove-Item -Force $zipPath
}

Compress-Archive -Path $stageRoot -DestinationPath $zipPath -CompressionLevel Optimal -Force

Write-Host "Package created:"
Write-Host "  $zipPath"
Write-Host ""
Write-Host "Contents:"
Write-Host "  $packageName/start.command"
Write-Host "  $packageName/README_MAC_LOCAL.txt"
Write-Host "  $packageName/app.py"
Write-Host "  $packageName/api/"
Write-Host "  $packageName/dbase/"
Write-Host "  $packageName/static/"
Write-Host "  $packageName/templates/"
Write-Host "  $packageName/requirements.txt"
