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

Write-Host "Stopping existing containers..."
docker compose down --remove-orphans 2>$null

# Ignore the case where the container/image was never created.
try {
    docker inspect nutriproof *> $null
    if ($LASTEXITCODE -eq 0) {
        docker rm -f nutriproof *> $null
    }
} catch {
    Write-Host "Container nutriproof not found; continuing."
}

try {
    docker image inspect nutriproof:latest *> $null
    if ($LASTEXITCODE -eq 0) {
        docker image rm -f nutriproof:latest *> $null
    }
} catch {
    Write-Host "Image nutriproof:latest not found; continuing."
}

Write-Host "Rebuilding Docker image..."
docker compose build --no-cache

Write-Host "Starting container..."
docker compose up -d

Write-Host "Checking French OCR model..."
docker exec nutriproof ls /usr/share/tesseract-ocr/5/tessdata | Select-String "fra"

$port = $env:PORT
if (-not $port) { $port = "8080" }
Write-Host "Container started. Open: http://localhost:$port"
