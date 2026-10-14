param(
    [string]$ProjectId = "imx-nutriproof"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Commande requise introuvable: $Name"
    }
}

Require-Command "firebase"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
$websiteDir = Join-Path $repoRoot "website"

if (-not (Test-Path $websiteDir)) {
    throw "Dossier website introuvable: $websiteDir"
}

Set-Location $websiteDir

$deployArgs = @("deploy", "--project", $ProjectId, "--only", "hosting:website")

Write-Host "==> Déploiement Firebase (projet: $ProjectId)"
Write-Host "NOTE: Ce script déploie website/public vers la cible hosting 'website' (imx-nutriproof.web.app)."
& firebase @deployArgs

Write-Host ""
Write-Host "Site website/public déployé ✅"
