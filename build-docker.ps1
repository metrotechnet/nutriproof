$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
        $name, $value = $_ -split '=', 2
        if (-not $name) { return }
        $name = $name.Trim()
        $value = $value.Trim()
        if ($value.StartsWith('"') -and $value.EndsWith('"')) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

$ImageName = $env:IMAGE_NAME
if (-not $ImageName) { $ImageName = "nutriproof:latest" }

$BuildContext = $env:BUILD_CONTEXT
if (-not $BuildContext) { $BuildContext = "." }

$Dockerfile = $env:DOCKERFILE
if (-not $Dockerfile) { $Dockerfile = "Dockerfile" }

Write-Host "Building Docker image: $ImageName"
Write-Host "Context: $BuildContext"
Write-Host "Dockerfile: $Dockerfile"

# Docker Desktop may reject rebuilding a tag that already exists in the local registry.
# Remove the old tag first so the new image can be exported cleanly.
try {
    docker image rm $ImageName 2>$null | Out-Null
} catch {}

docker build -t $ImageName -f $Dockerfile $BuildContext

if ($LASTEXITCODE -ne 0) {
    throw "Docker build failed"
}

Write-Host "Image built successfully: $ImageName"
