param(
    [string]$ProjectId = "nutriproof",
    [string]$Region = "northamerica-northeast1",
    [string]$Zone = "northamerica-northeast1-a",
    [string]$InstanceName = "nutriproof-vm",
    [string]$DiskName = "nutriproof-data",
    [int]$DiskSizeGb = 200,
    [string]$DiskType = "pd-ssd",
    [string]$MachineType = "e2-standard-4",
    [string]$RepoUrl = "https://github.com/metrotechnet/nutriproof.git",
    [string]$AppDir = "/opt/nutriproof",
    [string]$UploadRoot = "/mnt/nutriproof/uploads",
    [int]$AppPort = 8080,
    [string]$DomainName = "imxtech.ca",
    [string]$Subdomain = "nutriproof",
    [string]$DnsZoneName = "",
    [switch]$SkipFirewall,
    [switch]$SkipDns
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

function Require-Command {
    param([string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Command not found: $Name"
    }
}

function Invoke-GCloudChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args,
        [string]$Step = "gcloud command"
    )

    & gcloud @Args
    if ($LASTEXITCODE -ne 0) {
        throw "$Step failed (exit code: $LASTEXITCODE)."
    }
}

function Get-GCloudValue {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Args
    )

    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & gcloud @Args 2>$null
        if ($LASTEXITCODE -ne 0) { return "" }
        return ($output | Out-String).Trim()
    }
    finally {
        $ErrorActionPreference = $previousPreference
    }
}

function Ensure-StaticAddress {
    param(
        [string]$AddressName,
        [string]$RegionName,
        [string]$ProjectName
    )

    $existing = Get-GCloudValue -Args @("compute", "addresses", "describe", $AddressName, "--project", $ProjectName, "--region", $RegionName, "--format", "value(address)")
    if (-not $existing) {
        Invoke-GCloudChecked -Args @(
            "compute", "addresses", "create", $AddressName,
            "--project", $ProjectName,
            "--region", $RegionName
        ) -Step "Static IP creation"
        $existing = Get-GCloudValue -Args @("compute", "addresses", "describe", $AddressName, "--project", $ProjectName, "--region", $RegionName, "--format", "value(address)")
    }

    return $existing
}

function Ensure-DnsARecord {
    param(
        [string]$HostName,
        [string]$IpAddress,
        [string]$ProjectName,
        [string]$Domain,
        [string]$ZoneOverride
    )

    $managedZone = if ($ZoneOverride) { $ZoneOverride } else {
        Get-GCloudValue -Args @("dns", "managed-zones", "list", "--project", $ProjectName, "--filter", "dnsName=${Domain}.", "--format", "value(name)")
    }

    if (-not $managedZone) {
        Write-Warning "No Cloud DNS zone for '$Domain' was found in project '$ProjectName'. Add this record manually: $HostName -> $IpAddress"
        return
    }

    $recordName = "$HostName."
    $existing = Get-GCloudValue -Args @("dns", "record-sets", "list", "--project", $ProjectName, "--zone", $managedZone, "--name", $recordName, "--format", "value(rrdatas)")

    if (-not $existing) {
        Invoke-GCloudChecked -Args @(
            "dns", "record-sets", "create", $recordName,
            "--project", $ProjectName,
            "--zone", $managedZone,
            "--type", "A",
            "--ttl", "300",
            "--rrdatas", $IpAddress
        ) -Step "DNS A record creation"
        return
    }

    $existingValues = @($existing -split "[\r\n]+" | Where-Object { $_ -and $_.Trim() })
    if ($existingValues -contains $IpAddress) {
        Write-Host "DNS A record already points to $IpAddress for $HostName."
        return
    }

    Write-Host "Updating DNS A record for $HostName to $IpAddress"
    & gcloud dns record-sets transaction start --project $ProjectName --zone $managedZone 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to start DNS transaction for $HostName."
    }

    $removeArgs = @("dns", "record-sets", "transaction", "remove", $recordName, "--project", $ProjectName, "--zone", $managedZone, "--name", $recordName, "--type", "A", "--ttl", "300", "--rrdatas", $existingValues[0])
    & gcloud @removeArgs 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to remove existing DNS A record for $HostName."
    }

    & gcloud dns record-sets transaction add $recordName --project $ProjectName --zone $managedZone --type A --ttl 300 --rrdatas $IpAddress 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to add updated DNS A record for $HostName."
    }

    & gcloud dns record-sets transaction execute --project $ProjectName --zone $managedZone 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Unable to execute DNS transaction for $HostName."
    }
}

Require-Command "gcloud"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Split-Path -Parent $scriptDir
Set-Location $repoRoot

Write-Host "==> Setting GCP project: $ProjectId"
Invoke-GCloudChecked -Args @("config", "set", "project", $ProjectId) -Step "Project configuration"

Write-Host "==> Checking GCP billing"
$billing = Get-GCloudValue -Args @("billing", "projects", "describe", $ProjectId, "--format", "value(billingEnabled)")
if (-not $billing) {
    throw "Unable to verify billing for project '$ProjectId'. Ensure the project exists and you are logged in to the correct GCP account."
}
if ($billing.ToLowerInvariant() -ne "true") {
    throw "Billing is not enabled for project '$ProjectId'."
}

Write-Host "==> Ensuring persistent SSD disk exists: $DiskName"
$diskExists = Get-GCloudValue -Args @("compute", "disks", "describe", $DiskName, "--project", $ProjectId, "--zone", $Zone, "--format", "value(name)")
if (-not $diskExists) {
    Invoke-GCloudChecked -Args @(
        "compute", "disks", "create", $DiskName,
        "--project", $ProjectId,
        "--zone", $Zone,
        "--type", $DiskType,
        "--size", "${DiskSizeGb}GB"
    ) -Step "Disk creation"
}

Write-Host "==> Ensuring VM exists: $InstanceName"
$instanceExists = Get-GCloudValue -Args @("compute", "instances", "describe", $InstanceName, "--project", $ProjectId, "--zone", $Zone, "--format", "value(name)")
if (-not $instanceExists) {
    Invoke-GCloudChecked -Args @(
        "compute", "instances", "create", $InstanceName,
        "--project", $ProjectId,
        "--zone", $Zone,
        "--machine-type", $MachineType,
        "--image-family", "ubuntu-2204-lts",
        "--image-project", "ubuntu-os-cloud",
        "--boot-disk-size", "20GB",
        "--boot-disk-type", "pd-balanced",
        "--tags", "http-server,https-server"
    ) -Step "VM creation"
}

Write-Host "==> Ensuring VM is running"
& gcloud compute instances start $InstanceName --project $ProjectId --zone $Zone 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "VM $InstanceName is already running or could not be started."
}

Write-Host "==> Ensuring static external IP exists"
$staticIpName = "$($InstanceName)-ip"
$staticIp = Ensure-StaticAddress -AddressName $staticIpName -RegionName $Region -ProjectName $ProjectId

Write-Host "==> Assigning static IP to VM"
$instanceIp = Get-GCloudValue -Args @("compute", "instances", "describe", $InstanceName, "--project", $ProjectId, "--zone", $Zone, "--format", "value(networkInterfaces[0].accessConfigs[0].natIP)")
if ($instanceIp -ne $staticIp) {
    $attachCmd = @(
        "compute", "instances", "network-interfaces", "update", $InstanceName,
        "--project", $ProjectId,
        "--zone", $Zone,
        "--network-interface", "nic0",
        "--public-ip", $staticIpName
    )
    & gcloud @attachCmd 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Static IP assignment command returned a non-zero exit code. You can re-run the script or set the IP manually."
    }
}

Write-Host "==> Attaching disk to VM"
$instanceDiskNames = Get-GCloudValue -Args @("compute", "instances", "describe", $InstanceName, "--project", $ProjectId, "--zone", $Zone, "--format", "value(disks[].deviceName)")
$diskMatches = @()
if ($instanceDiskNames) {
    $diskMatches = @($instanceDiskNames -split "[;\r\n]+" | Where-Object { $_ -eq $DiskName })
}
$attached = $diskMatches.Count -gt 0
if (-not $attached) {
    $attachResult = & gcloud compute instances attach-disk $InstanceName --project $ProjectId --zone $Zone --disk $DiskName --device-name $DiskName --mode rw 2>&1
    if ($LASTEXITCODE -ne 0) {
        $msg = ($attachResult | Out-String)
        if ($msg -match "already being used by") {
            Write-Host "Disk $DiskName is already attached to $InstanceName."
        }
        else {
            throw "Disk attachment failed: $msg"
        }
    }
}
else {
    Write-Host "Disk $DiskName is already attached to $InstanceName."
}

if (-not $SkipFirewall) {
    Write-Host "==> Allowing inbound TCP/$AppPort"
    $ruleName = "allow-$($InstanceName)-$AppPort"
    $ruleExists = Get-GCloudValue -Args @("compute", "firewall-rules", "describe", $ruleName, "--project", $ProjectId, "--format", "value(name)")
    if (-not $ruleExists) {
        Invoke-GCloudChecked -Args @(
            "compute", "firewall-rules", "create", $ruleName,
            "--project", $ProjectId,
            "--direction", "INGRESS",
            "--priority", "1000",
            "--network", "default",
            "--action", "ALLOW",
            "--rules", "tcp:$AppPort",
            "--source-ranges", "0.0.0.0/0",
            "--target-tags", "http-server"
        ) -Step "Firewall rule creation"
    }
}

Write-Host "==> Installing Docker and mounting persistent disk on the VM"
$devicePath = "/dev/disk/by-id/google-$DiskName"
$remoteScriptPath = Join-Path $env:TEMP ("nutriproof-vm-setup-" + [System.Guid]::NewGuid().ToString('N') + ".sh")
$remoteScript = @'
#!/usr/bin/env bash
set -Eeuo pipefail

sudo apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  ca-certificates \
  curl \
  gnupg \
  git \
  docker.io \
  docker-compose

sudo systemctl enable --now docker
sudo usermod -aG docker "$(id -un)"

DEVICE="__DEVICE_PATH__"
if [ ! -e "$DEVICE" ]; then
  echo "Disk device not found: $DEVICE" >&2
  exit 1
fi

if ! sudo blkid "$DEVICE" >/dev/null 2>&1; then
  sudo mkfs.ext4 -F "$DEVICE"
fi

sudo mkdir -p /mnt/nutriproof
if ! mount | grep -q ' on /mnt/nutriproof '; then
  sudo mount "$DEVICE" /mnt/nutriproof
fi

sudo mkdir -p "__UPLOAD_ROOT__"
sudo chown -R "$(id -un):$(id -gn)" /mnt/nutriproof

sudo mkdir -p /opt
sudo chown -R "$(id -un):$(id -gn)" /opt

if [ ! -d "__APP_DIR__/.git" ]; then
  git clone "__REPO_URL__" "__APP_DIR__"
else
  cd "__APP_DIR__" && git pull --ff-only
fi

cat > "__APP_DIR__/.env" <<EOF_ENV
UPLOAD_ROOT=__UPLOAD_ROOT__
PORT=__APP_PORT__
EOF_ENV

cd "__APP_DIR__"
if docker compose version >/dev/null 2>&1; then
  docker compose up -d --build
else
  docker-compose up -d --build
fi

# Persist the mount across reboots.
UUID_VALUE="$(sudo blkid -s UUID -o value "$DEVICE")"
sudo sh -c "echo 'UUID=$UUID_VALUE /mnt/nutriproof ext4 defaults,nofail 0 2' >> /etc/fstab"

# Ensure the app starts automatically after a VM reboot.
cat > /etc/systemd/system/nutriproof-app.service <<SERVICE
[Unit]
Description=NutriProof App
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory="__APP_DIR__"
ExecStart=/bin/bash -lc 'cd "__APP_DIR__" && if docker compose version >/dev/null 2>&1; then docker compose up -d --build; else docker-compose up -d --build; fi'
ExecStop=/bin/bash -lc 'cd "__APP_DIR__" && (docker compose down || docker-compose down || true)'

[Install]
WantedBy=multi-user.target
SERVICE

sudo systemctl daemon-reload
sudo systemctl enable --now nutriproof-app.service

mkdir -p "__UPLOAD_ROOT__"

APP_PORT="__APP_PORT__"

echo "VM initialization complete"

echo "App URL: http://$(hostname -I | awk '{print $1}'):${APP_PORT}"
'@

$remoteScript = $remoteScript.Replace("__DEVICE_PATH__", $devicePath)
$remoteScript = $remoteScript.Replace("__REPO_URL__", $RepoUrl)
$remoteScript = $remoteScript.Replace("__APP_DIR__", $AppDir)
$remoteScript = $remoteScript.Replace("__UPLOAD_ROOT__", $UploadRoot)
$remoteScript = $remoteScript.Replace("__APP_PORT__", [string]$AppPort)
$remoteScript = $remoteScript -replace "`r`n", "`n" -replace "`r", "`n"

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($remoteScriptPath, $remoteScript, $utf8NoBom)

& gcloud compute scp $remoteScriptPath "${InstanceName}:/tmp/nutriproof-vm-setup.sh" --project $ProjectId --zone $Zone --quiet
if ($LASTEXITCODE -ne 0) {
    Remove-Item $remoteScriptPath -Force -ErrorAction SilentlyContinue
    throw "Failed to copy VM setup script to the instance."
}

& gcloud compute ssh $InstanceName --project $ProjectId --zone $Zone --ssh-key-file ~/.ssh/google_compute_engine --strict-host-key-checking=no --command "chmod +x /tmp/nutriproof-vm-setup.sh && sudo bash /tmp/nutriproof-vm-setup.sh"
if ($LASTEXITCODE -ne 0) {
    Remove-Item $remoteScriptPath -Force -ErrorAction SilentlyContinue
    throw "VM provisioning failed."
}

Remove-Item $remoteScriptPath -Force -ErrorAction SilentlyContinue

$ip = (& gcloud compute instances describe $InstanceName --project $ProjectId --zone $Zone --format "value(networkInterfaces[0].accessConfigs[0].natIP)" 2>$null | Out-String).Trim()
if (-not $ip) {
    $ip = (& gcloud compute instances describe $InstanceName --project $ProjectId --zone $Zone --format "value(networkInterfaces[0].networkIP)" 2>$null | Out-String).Trim()
}

if (-not $SkipDns) {
    $hostname = if ($Subdomain) { "$Subdomain.$DomainName" } else { $DomainName }
    Write-Host "==> Updating DNS record for $hostname"
    Ensure-DnsARecord -HostName $hostname -IpAddress $ip -ProjectName $ProjectId -Domain $DomainName -ZoneOverride $DnsZoneName
}

Write-Host ""
Write-Host "Deployment complete ✅"
Write-Host "VM: $InstanceName"
Write-Host "IP: $ip"
Write-Host "Upload root: $UploadRoot"
Write-Host "App: http://${ip}:$AppPort"
if (-not $SkipDns) {
    Write-Host "DNS: http://$hostname"
}
