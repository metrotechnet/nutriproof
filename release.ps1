# release.ps1 — Bump version, commit, tag, and push to trigger CI/CD build
# Compatible with older PowerShell / Windows environments and the macOS DMG compatibility fix.
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d+\.\d+\.\d+$')]
    [string]$Version,

    [Parameter(Mandatory = $false)]
    [switch]$IncludeUploads
)

$ErrorActionPreference = 'Stop'

$tag = "v$Version"

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
    Write-Host "Tag $tag already exists. Skipping tag creation." -ForegroundColor Yellow
}

Write-Host "Pushing main branch to origin..." -ForegroundColor Cyan
try {
    & git push origin main 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git push origin main failed" }
}
catch {
    Write-Error "Git push to origin/main failed. Check GitHub auth, repo permissions, and branch protection."
    Write-Error $_.Exception.Message
    throw
}

Write-Host "Pushing tag $tag to origin..." -ForegroundColor Cyan
try {
    & git push origin $tag 2>&1
    if ($LASTEXITCODE -ne 0) { throw "git push origin $tag failed" }
}
catch {
    Write-Error "Git push for tag $tag failed. Check GitHub auth, repo permissions, and tag protection."
    Write-Error $_.Exception.Message
    throw
}

# Trigger workflow_dispatch with optional inputs
if ($IncludeUploads) {
    Write-Host ""
    Write-Host "Triggering GitHub Actions with include_uploads=true..." -ForegroundColor Cyan
    
    $workflowInput = @{
        include_uploads = 'true'
    } | ConvertTo-Json
    
    $gh_args = @(
        'workflow', 'run',
        'build.yml',
        '--ref', 'main',
        '--raw-field', "inputs=$workflowInput"
    )
    
    Invoke-CheckedCommand -Command 'gh' -Arguments $gh_args
    Write-Host "Workflow dispatched with uploads packaging enabled." -ForegroundColor Green
}

Write-Host ""
Write-Host "Release $tag pushed. GitHub Actions build started." -ForegroundColor Cyan
Write-Host "Track progress: https://github.com/metrotechnet/nutriproof/actions" -ForegroundColor Cyan
