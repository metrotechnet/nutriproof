param(
    [string]$ProjectId = "nutriproof",
    [string]$Region = "northamerica-northeast1",
    [string]$ServiceName = "nutriproof-api",
    [string]$ArtifactRepo = "nutriproof",
    [string]$ImageTag = "latest",
    [string]$ImageUri = "",
    [string]$Cpu = "4",
    [string]$Memory = "8Gi",
    [int]$Concurrency = 80,
    [int]$MinInstances = 0,
    [int]$MaxInstances = 100,
    [int]$TimeoutSeconds = 300,
    [ValidateSet("local", "gcs")]
    [string]$StorageMode = "local",
    [string]$GcsBucket = "",
    [string]$GcsPrefix = "uploads",
    [switch]$AlwaysAllocatedCpu,
    [switch]$AllowUnauthenticated
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

Write-Host "==> Vérification du projet GCP et de la facturation"
$billingOutput = & gcloud billing projects describe $ProjectId --format "value(billingEnabled)"
if ($LASTEXITCODE -ne 0) {
    throw "Impossible de vérifier la facturation du projet '$ProjectId'. Vérifie que le projet existe et que tu es authentifié sur le bon compte GCP."
}
if (($billingOutput | Out-String).Trim().ToLowerInvariant() -ne "true") {
    throw "La facturation n'est pas activée pour le projet '$ProjectId'. Active-la dans la console GCP: https://console.cloud.google.com/billing/linkedaccount?project=$ProjectId"
}

Write-Host "==> Vérification du bucket GCS (désactivée: stockage local uniquement)"

Write-Host "==> Activation des APIs GCP nécessaires au déploiement"
Invoke-GCloudChecked -Args @(
    "services", "enable",
    "run.googleapis.com"
) -Step "Activation des APIs"

$image = if ($ImageUri) { $ImageUri } else { "$Region-docker.pkg.dev/$ProjectId/$ArtifactRepo/$ServiceName`:$ImageTag" }
if ($StorageMode -eq "gcs" -and [string]::IsNullOrWhiteSpace($GcsBucket)) {
    throw "StorageMode=gcs requires -GcsBucket to be set."
}

$envVars = @("UPLOAD_ROOT=/tmp/uploads", "STORAGE_MODE=$StorageMode")
if ($StorageMode -eq "gcs") {
    $envVars += "GCS_BUCKET=$GcsBucket"
    $envVars += "GCS_PREFIX=$GcsPrefix"
}

$deployArgs = @(
    "run", "deploy", $ServiceName,
    "--image", $image,
    "--platform", "managed",
    "--region", $Region,
    "--set-env-vars", ($envVars -join ","),
    "--cpu", $Cpu,
    "--memory", $Memory,
    "--concurrency", "$Concurrency",
    "--min-instances", "$MinInstances",
    "--max-instances", "$MaxInstances",
    "--timeout", "$TimeoutSeconds"
)

if ($AlwaysAllocatedCpu) {
    $deployArgs += "--no-cpu-throttling"
}

if ($AllowUnauthenticated) {
    $deployArgs += "--allow-unauthenticated"
} else {
    $deployArgs += "--no-allow-unauthenticated"
}

Write-Host "==> Déploiement Cloud Run: $ServiceName"
Invoke-GCloudChecked -Args $deployArgs -Step "Déploiement Cloud Run"

$serviceUrl = gcloud run services describe $ServiceName --region $Region --format "value(status.url)"
if ($LASTEXITCODE -ne 0) {
    throw "Déploiement terminé mais impossible de lire l'URL du service Cloud Run."
}
$serviceUrl = ($serviceUrl | Out-String).Trim()
if (-not $serviceUrl) {
    throw "Déploiement Cloud Run incomplet: URL du service vide."
}
Write-Host ""
Write-Host "API déployée ✅"
Write-Host "URL: $serviceUrl"
