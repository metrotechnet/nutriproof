param(
    [string]$ProjectId = "nutriproof-imx",
    [switch]$HostingOnly
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$newScript = Join-Path $scriptDir "deploy-website-static.ps1"
if (-not (Test-Path $newScript)) {
    throw "Script introuvable: $newScript"
}

Write-Warning "Le script deploy-gcp-frontend.ps1 est déprécié. Utilisez scripts/deploy-website-static.ps1."
& $newScript -ProjectId $ProjectId -HostingOnly:$HostingOnly
