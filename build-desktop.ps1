<#
.SYNOPSIS
    Build script for NutriProof Electron desktop app (Windows).
.DESCRIPTION
    1. Bundles the Python/Flask backend with PyInstaller
    2. Copies Tesseract OCR into a bundle folder
    3. Creates uploads/ folder in the backend dist
    4. Packages the app:
       - Default: portable folder with electron-packager
       - -Installer: NSIS installer with electron-builder (supports auto-update)
       - -Publish: also uploads to GitHub Releases for auto-update
#>

param(
    [string]$TesseractSource = "C:\Program Files\Tesseract-OCR",
    [switch]$SkipBackend,
    [switch]$SkipElectron,
    [switch]$Installer,
    [switch]$Publish
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "=== NutriProof Build ===" -ForegroundColor Cyan
Write-Host "Project root: $ProjectRoot"

# -------------------------------------------------------------------
# Step 1: Bundle Python backend with PyInstaller
# -------------------------------------------------------------------
if (-not $SkipBackend) {
    Write-Host "`n--- Step 1: Building Python backend with PyInstaller ---" -ForegroundColor Yellow

    Push-Location $ProjectRoot

    # Activate venv
    $venvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-Error "Virtual environment not found at .venv\. Create it first: python -m venv .venv"
    }

    # Ensure PyInstaller is installed
    & $venvPython -m pip install pyinstaller --quiet

    # Clean previous build
    if (Test-Path "dist\backend") { Remove-Item -Recurse -Force "dist\backend" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

    # Run PyInstaller
    & $venvPython -m PyInstaller app.spec --noconfirm
    if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller failed" }

    # Create uploads folder in dist
    $uploadsDir = Join-Path $ProjectRoot "dist\backend\uploads\main"
    New-Item -ItemType Directory -Force -Path $uploadsDir | Out-Null

    Pop-Location
    Write-Host "Backend build complete." -ForegroundColor Green
}

# -------------------------------------------------------------------
# Step 2: Bundle Tesseract OCR
# -------------------------------------------------------------------
Write-Host "`n--- Step 2: Bundling Tesseract OCR ---" -ForegroundColor Yellow

$tesseractDest = Join-Path $ProjectRoot "tesseract-bundle"
if (Test-Path $tesseractDest) { Remove-Item -Recurse -Force $tesseractDest }

if (-not (Test-Path $TesseractSource)) {
    Write-Error "Tesseract not found at $TesseractSource. Install it or pass -TesseractSource <path>"
}

Write-Host "Copying Tesseract from $TesseractSource ..."
Copy-Item -Recurse -Force $TesseractSource $tesseractDest
Write-Host "Tesseract bundled." -ForegroundColor Green

# -------------------------------------------------------------------
# Step 3: Build Electron package
# -------------------------------------------------------------------
if (-not $SkipElectron) {
    Write-Host "`n--- Step 3: Building Electron package ---" -ForegroundColor Yellow

    Push-Location (Join-Path $ProjectRoot "electron")

    # Install npm dependencies
    npm install
    if ($LASTEXITCODE -ne 0) { Write-Error "npm install failed" }

    if ($Installer) {
        # Build with electron-builder (NSIS installer + auto-update support)
        if ($Publish) {
            Write-Host "Building installer + publishing to GitHub Releases..." -ForegroundColor Cyan
            npm run dist-publish
        } else {
            Write-Host "Building installer (local only)..." -ForegroundColor Cyan
            npm run dist
        }
    } else {
        # Package with electron-packager (portable folder)
        npm run pack
    }
    if ($LASTEXITCODE -ne 0) { Write-Error "Electron build failed" }

    Pop-Location
    Write-Host "Electron build complete." -ForegroundColor Green
}

# -------------------------------------------------------------------
# Done
# -------------------------------------------------------------------
if ($Installer) {
    $outputDir = Join-Path $ProjectRoot "dist\electron"
    Write-Host "`n=== Build finished ===" -ForegroundColor Cyan
    Write-Host "Installer output: $outputDir"
    $nsis = Get-ChildItem $outputDir -Filter "*.exe" -File | Where-Object { $_.Name -match "Setup" } | Select-Object -First 1
    if ($nsis) {
        $sizeMB = [math]::Round($nsis.Length / 1MB, 1)
        Write-Host "  Installer: $($nsis.Name) ($sizeMB MB)"
    }
    if ($Publish) {
        Write-Host "  Published to GitHub Releases" -ForegroundColor Green
    }
} else {
    $outputDir = Join-Path $ProjectRoot "dist\electron\NutriProof-win32-x64"
    Write-Host "`n=== Build finished ===" -ForegroundColor Cyan
    Write-Host "Package output: $outputDir"
    if (Test-Path $outputDir) {
        $totalMB = [math]::Round((Get-ChildItem $outputDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
        Write-Host "  Total size: $totalMB MB"
        Write-Host "  Executable: NutriProof.exe"
    }
}
