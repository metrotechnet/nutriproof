param(
    [string]$ProjectId = "nutriproof-web",
    [string]$HostingSite = "nutriproof-web"
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

Write-Host "==> Sélection du projet Firebase actif: $ProjectId"
& firebase use $ProjectId
if ($LASTEXITCODE -ne 0) {
    throw "La commande firebase use a échoué."
}

$deployArgs = @("deploy", "--project", $ProjectId, "--only", "hosting:app")
Write-Host "==> Déploiement Firebase (projet: $ProjectId)"
Write-Host "NOTE: Ce script déploie la cible hosting 'app' pour le site https://$HostingSite.web.app avec rewrite vers Cloud Run."
& firebase @deployArgs
if ($LASTEXITCODE -ne 0) {
    throw "Le déploiement Firebase a échoué."
}

Write-Host ""
Write-Host "Cible hosting:app déployée ✅"
Write-Host "URL: https://$HostingSite.web.app"
