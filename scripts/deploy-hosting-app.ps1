param(
    [string]$ProjectId = "nutriproof-imx"
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

$deployArgs = @("deploy", "--project", $ProjectId, "--only", "hosting:app")

Write-Host "==> Déploiement Firebase (projet: $ProjectId)"
Write-Host "NOTE: Ce script déploie la cible hosting 'app' (nutriproof-imx.web.app) avec rewrite vers Cloud Run."
& firebase @deployArgs

Write-Host ""
Write-Host "Cible hosting:app déployée ✅"
