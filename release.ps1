# release.ps1 — Bump version, commit, tag, and push to trigger CI/CD build
# Compatible with older PowerShell / Windows environments and the macOS DMG compatibility fix.
param(
    [Parameter(Mandatory = $false)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory = $false)]
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

if (-not $Version) {
    $appPath = Join-Path $PSScriptRoot 'app.py'
    if (Test-Path $appPath) {
        $appText = [System.IO.File]::ReadAllText($appPath)
        $appMatch = [regex]::Match($appText, 'APP_VERSION\s*=\s*[''\"](?<version>\d+\.\d+\.\d+)[''\"]')
        if ($appMatch.Success) {
            $Version = $appMatch.Groups['version'].Value
        }
    }
}

if (-not $Version) {
    $pkgPath = Join-Path $PSScriptRoot 'electron\package.json'
    if (Test-Path $pkgPath) {
        try {
            $pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
            if ($pkg.version) {
                $Version = [string]$pkg.version
            }
        }
        catch {
            # ignore JSON read issues and fall through to a clear validation error below
        }
    }
}

if (-not $Version) {
    throw "Version is required. Pass -Version or ensure app.py/electron/package.json contains a valid semantic version."
}

$tag = "v$Version"
$dryRun = $WhatIf.IsPresent

if ($dryRun) {
    Write-Host "Dry run enabled. No version files, git commits, tags, pushes, or workflow dispatches will be changed." -ForegroundColor Yellow
    Write-Host "Release version: $Version" -ForegroundColor Cyan
    Write-Host "Git tag: $tag" -ForegroundColor Cyan
    return
}

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,

        [Parameter(Mandatory = $false)]
        [string[]]$Arguments = @(),

        [Parameter(Mandatory = $false)]
        [string[]]$AllowedMessages = @()
    )

    $previousErrorPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        # Git often writes progress to stderr even when the command succeeds (for example
        # `To https://...` during push). Redirecting stderr prevents PowerShell from surfacing
        # those non-fatal lines as false-native-command errors while still capturing stdout.
        $output = & $Command @Arguments 2>$null
        $exitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorPreference
    }

    $text = if ($null -ne $output) { ($output | Out-String).Trim() } else { '' }
    if ($text) { Write-Host $text }

    if ($exitCode -ne 0) {
        foreach ($pattern in $AllowedMessages) {
            if ($text -match $pattern) {
                Write-Warning "Command returned a non-zero exit code but matched an allowed message: $pattern"
                return
            }
        }
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

$branchName = (& git branch --show-current 2>$null)
if ($branchName -and $branchName -ne 'main') {
    Write-Error "Release must be run from the main branch. Current branch: $branchName"
    throw "Release aborted: wrong branch ($branchName)"
}

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

# Keep the DMG format consistent with the old macOS compatibility requirement.
# The format property lives under build.dmg, not under build.mac.target entries.
$pkg = Get-Content $pkgPath -Raw | ConvertFrom-Json
if (-not $pkg.build) { $pkg | Add-Member -NotePropertyName build -NotePropertyValue ([pscustomobject]@{}) }
if (-not $pkg.build.dmg) { $pkg.build | Add-Member -NotePropertyName dmg -NotePropertyValue ([pscustomobject]@{}) }
$pkg.build.dmg.format = 'UDZO'
$json = $pkg | ConvertTo-Json -Depth 20
[System.IO.File]::WriteAllText($pkgPath, $json, [System.Text.UTF8Encoding]::new($false))
Write-Host "Ensured macOS DMG format compatibility (UDZO)" -ForegroundColor Green

# Stage, commit, tag, push
$gitStatus = (& git status --porcelain 2>$null)
$tagExists = (& git rev-parse --verify --quiet "refs/tags/$tag" 2>$null)
$headMessage = (& git log -1 --pretty=%s 2>$null)

if ($gitStatus) {
    Invoke-CheckedCommand -Command 'git' -Arguments @('add', '-A')
    Invoke-CheckedCommand -Command 'git' -Arguments @('commit', '-m', "release: $tag")
}
elseif ($headMessage -eq "release: $tag") {
    Write-Host "Release commit for $tag already exists and the working tree is clean. Skipping commit." -ForegroundColor Yellow
}
else {
    Write-Host "Working tree is clean. No new commit required for $tag." -ForegroundColor Yellow
}

if (-not $tagExists) {
    Invoke-CheckedCommand -Command 'git' -Arguments @('tag', $tag)
}
else {
    Write-Error "Tag $tag already exists locally. Remove it with 'git tag -d $tag' or choose a new version before running the release again."
    throw "Release aborted: duplicate tag $tag"
}

Invoke-CheckedCommand -Command 'git' -Arguments @('push', 'origin', 'main') -AllowedMessages @('Everything up-to-date', 'up-to-date')
Invoke-CheckedCommand -Command 'git' -Arguments @('push', 'origin', $tag) -AllowedMessages @('Everything up-to-date', 'already exists', 'up-to-date')

Write-Host ""
Write-Host "Release $tag pushed. GitHub Actions build will start automatically on the tag push." -ForegroundColor Cyan
Write-Host "Track progress: https://github.com/metrotechnet/nutriproof/actions" -ForegroundColor Cyan
