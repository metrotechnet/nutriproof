<#
.SYNOPSIS
    Build script for NutriProof Electron desktop app (Windows).
.DESCRIPTION
    1. Bundles the Python/Flask backend with PyInstaller
    2. Copies Tesseract OCR into a bundle folder
    3. Removes any stale upload folders from the backend dist
    4. Packages the app:
       - Default: portable folder with electron-packager
       - -Installer: NSIS installer with electron-builder (supports auto-update)
       - -Publish: also uploads to GitHub Releases for auto-update
    5. Optional: signs the NSIS installer using Microsoft Trusted Signing
#>

param(
    [string]$TesseractSource = "C:\Program Files\Tesseract-OCR",
    [switch]$SkipBackend,
    [switch]$SkipElectron,
    [switch]$Installer,
    [switch]$Publish,
    [Alias("SignWithArtifactSigning")]
    [switch]$SignWithTrustedSigning,
    [string]$TrustedSigningDlibPath,
    [string]$TrustedSigningMetadataPath,
    [string]$TimestampUrl = "http://timestamp.acs.microsoft.com/"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if ($SignWithTrustedSigning -and -not $Installer) {
    Write-Error "-SignWithTrustedSigning requires -Installer because only NSIS output (.exe) is signed by this script."
}

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

    # Remove any stale upload folders from dist to avoid bundling them
    $staleUploadDirs = @(
        (Join-Path $ProjectRoot "dist\backend\uploads"),
        (Join-Path $ProjectRoot "dist\backend\uploads - Copie")
    )
    foreach ($dir in $staleUploadDirs) {
        if (Test-Path $dir) {
            Remove-Item -Recurse -Force $dir
        }
    }

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
        $installerOutputDir = Join-Path $ProjectRoot "dist\electron"

        # Ensure deterministic output by removing stale setup installers from prior runs.
        if (Test-Path $installerOutputDir) {
            Get-ChildItem $installerOutputDir -Filter "*Setup*.exe" -File -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue
        }

        # Disable code signing (avoids winCodeSign symlink errors on Windows)
        $env:CSC_IDENTITY_AUTO_DISCOVERY = "false"

        # Pre-populate winCodeSign cache to avoid symlink extraction errors.
        # Windows cannot create symlinks without Developer Mode; the archive
        # contains macOS symlinks that fail on standard Windows setups.
        $wcsCacheDir = Join-Path $env:LOCALAPPDATA "electron-builder\Cache\winCodeSign\winCodeSign-2.6.0"
        if (-not (Test-Path $wcsCacheDir)) {
            Write-Host "Pre-populating winCodeSign cache..." -ForegroundColor Gray
            $wcsUrl = "https://github.com/electron-userland/electron-builder-binaries/releases/download/winCodeSign-2.6.0/winCodeSign-2.6.0.7z"
            $wcsParent = Split-Path $wcsCacheDir -Parent
            New-Item -ItemType Directory -Force -Path $wcsParent | Out-Null
            $wcs7z = Join-Path $wcsParent "winCodeSign-2.6.0.7z"
            Invoke-WebRequest -Uri $wcsUrl -OutFile $wcs7z
            $sevenZip = Join-Path $ProjectRoot "electron\node_modules\7zip-bin\win\x64\7za.exe"
            # 7z will warn about macOS symlinks it cannot create on Windows; ignore those warnings
            $ErrorActionPreference = "Continue"
            & $sevenZip x -bd $wcs7z "-o$wcsCacheDir" 2>$null
            $ErrorActionPreference = "Stop"
            # Fix macOS symlinks that could not be created (copy real files over 0-byte placeholders)
            $darwinLib = Join-Path $wcsCacheDir "darwin\10.12\lib"
            if (Test-Path $darwinLib) {
                Copy-Item (Join-Path $darwinLib "libcrypto.1.0.0.dylib") (Join-Path $darwinLib "libcrypto.dylib") -Force -ErrorAction SilentlyContinue
                Copy-Item (Join-Path $darwinLib "libssl.1.0.0.dylib") (Join-Path $darwinLib "libssl.dylib") -Force -ErrorAction SilentlyContinue
            }
            Remove-Item $wcs7z -ErrorAction SilentlyContinue
            Write-Host "winCodeSign cache ready." -ForegroundColor Green
        }

        # Build with electron-builder (NSIS installer + auto-update support)
        if ($Publish) {
            # Load GH_TOKEN from .env if not already set
            if (-not $env:GH_TOKEN) {
                $envFile = Join-Path $ProjectRoot ".env"
                if (Test-Path $envFile) {
                    Get-Content $envFile | ForEach-Object {
                        if ($_ -match '^\s*([^#][^=]+?)\s*=\s*(.+)$') {
                            [System.Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), "Process")
                        }
                    }
                }
            }
            if (-not $env:GH_TOKEN) {
                Write-Error "GH_TOKEN not found. Set it in .env or run: `$env:GH_TOKEN = 'ghp_...'"
            }
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
    $canonicalInstallerName = "NutriProof-Setup.exe"
    $canonicalInstallerPath = Join-Path $outputDir $canonicalInstallerName

    $setupInstallers = Get-ChildItem $outputDir -Filter "*Setup*.exe" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending
    if (-not $setupInstallers -or $setupInstallers.Count -eq 0) {
        Write-Error "No installer matching '*Setup*.exe' found in $outputDir"
    }

    $primaryInstaller = $setupInstallers | Select-Object -First 1
    if ($primaryInstaller.Name -ne $canonicalInstallerName) {
        Move-Item -Path $primaryInstaller.FullName -Destination $canonicalInstallerPath -Force
    }

    Get-ChildItem $outputDir -Filter "*Setup*.exe" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne $canonicalInstallerName } |
        Remove-Item -Force -ErrorAction SilentlyContinue

    $nsisInstallers = Get-ChildItem $outputDir -Filter $canonicalInstallerName -File -ErrorAction SilentlyContinue
    $nsis = $nsisInstallers | Select-Object -First 1

    Write-Host "`n=== Build finished ===" -ForegroundColor Cyan
    Write-Host "Installer output: $outputDir"
    if ($nsis) {
        $sizeMB = [math]::Round($nsis.Length / 1MB, 1)
        Write-Host "  Installer: $($nsis.Name) ($sizeMB MB)"
    }
    if ($Publish) {
        Write-Host "  Published to GitHub Releases" -ForegroundColor Green
    }

    if ($SignWithTrustedSigning) {
        if (-not $nsis) {
            Write-Error "Installer not found: $canonicalInstallerPath"
        }

        if (-not $TrustedSigningDlibPath) {
            Write-Error "Trusted Signing dlib path missing. Pass -TrustedSigningDlibPath <path-to-Azure.CodeSigning.Dlib.dll>"
        }
        if (-not $TrustedSigningMetadataPath) {
            Write-Error "Trusted Signing metadata path missing. Pass -TrustedSigningMetadataPath <path-to-metadata.json>"
        }

        $resolvedDlib = if ([System.IO.Path]::IsPathRooted($TrustedSigningDlibPath)) {
            $TrustedSigningDlibPath
        } else {
            Join-Path $ProjectRoot $TrustedSigningDlibPath
        }

        $resolvedMetadata = if ([System.IO.Path]::IsPathRooted($TrustedSigningMetadataPath)) {
            $TrustedSigningMetadataPath
        } else {
            Join-Path $ProjectRoot $TrustedSigningMetadataPath
        }

        if (-not (Test-Path $resolvedDlib)) {
            Write-Error "Trusted Signing dlib not found: $resolvedDlib"
        }
        if (-not (Test-Path $resolvedMetadata)) {
            Write-Error "Trusted Signing metadata not found: $resolvedMetadata"
        }

        $signtool = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe" -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1

        if (-not $signtool) {
            Write-Error "signtool.exe not found. Install Windows SDK on this machine first."
        }

        Write-Host "`n--- Step 4: Signing installer with Trusted Signing ---" -ForegroundColor Yellow
        Write-Host "Signing: $($nsis.Name)" -ForegroundColor Gray
        & $signtool.FullName sign /v /fd SHA256 /td SHA256 /tr $TimestampUrl /dlib $resolvedDlib /dmdf $resolvedMetadata $nsis.FullName
        if ($LASTEXITCODE -ne 0) { Write-Error "Installer signing failed: $($nsis.Name)" }

        Write-Host "Verifying Authenticode signature: $($nsis.Name)" -ForegroundColor Gray
        & $signtool.FullName verify /pa /v $nsis.FullName
        if ($LASTEXITCODE -ne 0) { Write-Error "Installer signature verification failed: $($nsis.Name)" }

        Write-Host "Trusted Signing complete: $($nsis.Name)" -ForegroundColor Green
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

env:
  AZURE_LOG_LEVEL: verbose
