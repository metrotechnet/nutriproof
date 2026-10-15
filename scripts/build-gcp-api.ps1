param(
    [string]$ProjectId = "nutriproof",
    [string]$Region = "northamerica-northeast1",
    [string]$ServiceName = "nutriproof-api",
    [string]$ArtifactRepo = "nutriproof",
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Commande requise introuvable: $Name"
    }
}

function Invoke-GCloudChecked {
    param(
        [Parameter(Mandatory=$true)]
        [string[]]$Args,
        [string]$Step = "Commande gcloud"
    )
    & gcloud @Args
    if ($LASTEXITCODE -ne 0) {
        throw "$Step a échoué (exit code: $LASTEXITCODE)."
    }
}

Require-Command "gcloud"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

Write-Host "==> Configuration du projet GCP: $ProjectId"
Invoke-GCloudChecked -Args @("config", "set", "project", $ProjectId) -Step "Configuration du projet"

Write-Host "==> Vérification de la facturation"
$billingOutput = & gcloud billing projects describe $ProjectId --format "value(billingEnabled)"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de vérifier la facturation du projet '$ProjectId'."
}
if (($billingOutput | Out-String).Trim().ToLowerInvariant() -ne "true") {
    throw "La facturation n'est pas activée pour le projet '$ProjectId'. Active-la dans la console GCP: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
}

Write-Host "==> Activation des APIs GCP nécessaires au build"
Invoke-GCloudChecked -Args @(
    "services", "enable",
    "cloudbuild.googleapis.com",
    "artifactregistry.googleapis.com"
) -Step "Activation des APIs"

$repoExists = $true
try {
    Invoke-GCloudChecked -Args @("artifacts", "repositories", "describe", $ArtifactRepo, "--location", $Region) -Step "Vérification du dépôt Artifact Registry"
} catch {
    $repoExists = $false
}

if (-not $repoExists) {
    Write-Host "==> Création du dépôt Artifact Registry: $ArtifactRepo ($Region)"
    Invoke-GCloudChecked -Args @(
        "artifacts", "repositories", "create", $ArtifactRepo,
        "--repository-format=docker",
        "--location=$Region",
        "--description=Images Docker NutriProof"
    ) -Step "Création du dépôt Artifact Registry"
}

$image = "$Region-docker.pkg.dev/$ProjectId/$ArtifactRepo/$ServiceName`:$ImageTag"

Write-Host "==> Build et push de l'image: $image"
Invoke-GCloudChecked -Args @("builds", "submit", "--tag", $image, ".") -Step "Build et push de l'image"

Write-Host ""
Write-Host "Image API buildée ✅"
Write-Host "Image: $image"
