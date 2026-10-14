param(
    [string]$ProjectId = "nutriproof-imx",
    [switch]$HostingOnly
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

$deployArgs = @("deploy", "--project", $ProjectId)
if ($HostingOnly) {
    $deployArgs += @("--only", "hosting")
}

Write-Host "==> Déploiement Firebase (projet: $ProjectId)"
Write-Host "NOTE: Ce script déploie le site statique contenu dans website/public (marketing/download)."
Write-Host "      L'interface applicative NutriProof (templates + static) est déployée avec l'API Cloud Run."
& firebase @deployArgs

Write-Host ""
Write-Host "Site website/public déployé ✅"
