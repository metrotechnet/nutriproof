# release.ps1 — Bump version, commit, tag, and push to trigger CI/CD build
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version
)

$ErrorActionPreference = 'Stop'

$tag = "v$Version"

# Check for uncommitted changes
$status = git status --porcelain
if ($status) {
    Write-Host "Uncommitted changes detected. Committing all changes..." -ForegroundColor Yellow
}

# Update version in electron/package.json
$pkgPath = Join-Path $PSScriptRoot 'electron\package.json'
$pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
$pkg.version = $Version
$json = $pkg | ConvertTo-Json -Depth 10
[System.IO.File]::WriteAllText($pkgPath, $json, [System.Text.UTF8Encoding]::new($false))
Write-Host "Updated electron/package.json -> $Version" -ForegroundColor Green

# Update version in app.py
$appPath = Join-Path $PSScriptRoot 'app.py'
$appContent = [System.IO.File]::ReadAllText($appPath)
$appContent = $appContent -replace "APP_VERSION = '[^']*'", "APP_VERSION = '$Version'"
[System.IO.File]::WriteAllText($appPath, $appContent, [System.Text.UTF8Encoding]::new($false))
Write-Host "Updated app.py -> $Version" -ForegroundColor Green

# Stage, commit, tag, push
git add -A
git commit -m "release: $tag"
git tag $tag
git push origin main
git push origin $tag

Write-Host ""
Write-Host "Release $tag pushed. GitHub Actions build started." -ForegroundColor Cyan
Write-Host "Track progress: https://github.com/metrotechnet/nutriproof/actions" -ForegroundColor Cyan
