
# LogShift - Automatic EC2 IP Updater
$ErrorActionPreference = "Stop"

# Configuration
$Region = "ap-southeast-2"
$SshUser = "ubuntu"
$SshKey = "D:\AWS key\logshift_kp.pem"
$RemoteDir = "/home/ubuntu/LogShift"
$EnvFile = Join-Path $PSScriptRoot "..\.env"

Write-Host "`nLogShift IP Updater" -ForegroundColor Cyan

# 1. Read EC2 Instance ID from local .env
$EnvText = [System.IO.File]::ReadAllText($EnvFile)

$Match = [regex]::Match(
    $EnvText,
    '(?m)^EC2_INSTANCE_ID=(.*)$'
)

if (-not $Match.Success) {
    throw "EC2_INSTANCE_ID not found in local .env"
}

$InstanceId = $Match.Groups[1].Value.Trim()

if ($InstanceId -notmatch '^i-[a-f0-9]+$') {
    throw "Invalid EC2 Instance ID in .env"
}

# 2. Fetch current EC2 information
Write-Host "Fetching EC2 information..." -ForegroundColor Cyan

$Info = & aws ec2 describe-instances `
    --region $Region `
    --instance-ids $InstanceId `
    --query "Reservations[0].Instances[0].[State.Name,PublicIpAddress,PrivateIpAddress]" `
    --output json | ConvertFrom-Json

if ($LASTEXITCODE -ne 0) {
    throw "AWS CLI failed to retrieve instance information."
}

$State = $Info[0]
$PublicIp = $Info[1]
$PrivateIp = $Info[2]

if ($State -ne "running" -or
    $PublicIp -notmatch '^\d{1,3}(\.\d{1,3}){3}$' -or
    $PrivateIp -notmatch '^\d{1,3}(\.\d{1,3}){3}$') {
    throw "EC2 is not running or its IP addresses are unavailable."
}

Write-Host "Public IP:  $PublicIp" -ForegroundColor Green
Write-Host "Private IP: $PrivateIp" -ForegroundColor Green

# 3. Build ALLOWED_HOSTS, preserving non-IP entries
$HostsMatch = [regex]::Match(
    $EnvText,
    '(?m)^ALLOWED_HOSTS=(.*)$'
)

if (-not $HostsMatch.Success) {
    throw "ALLOWED_HOSTS not found in local .env"
}

$ExistingHosts = $HostsMatch.Groups[1].Value -split ',' |
    ForEach-Object { $_.Trim() } |
    Where-Object {
        $_ -and $_ -notmatch '^\d{1,3}(\.\d{1,3}){3}$'
    }

$AllowedHosts = @(
    $ExistingHosts
    $PublicIp
    $PrivateIp
    "localhost"
    "127.0.0.1"
) | Select-Object -Unique

$AllowedHostsString = $AllowedHosts -join ','

# 4. Update EC2 .env and recreate web container
Write-Host "`nUpdating EC2 configuration..." -ForegroundColor Cyan
$Target = "$SshUser@$PublicIp"
$CurrentImage = & ssh -i $SshKey -o ConnectTimeout=15 $Target `
    "docker inspect logshift-web --format '{{.Config.Image}}'"

if ($LASTEXITCODE -ne 0 -or -not $CurrentImage) {
    throw "Could not identify the currently deployed image."
}

$CurrentTag = ($CurrentImage.Trim() -split ':')[-1]

if ($CurrentTag -notmatch '^[0-9a-f]{40}$') {
    throw "Invalid deployed image tag. Refusing to use latest."
}

Write-Host "Preserving deployed version: $CurrentTag" -ForegroundColor Green

$RemoteCommand = "grep -q '^ALLOWED_HOSTS=' $RemoteDir/.env && sed -i 's|^ALLOWED_HOSTS=.*|ALLOWED_HOSTS=$AllowedHostsString|' $RemoteDir/.env && cd $RemoteDir && IMAGE_TAG=$CurrentTag docker compose -f docker-compose.prod.yml up -d --force-recreate web && docker compose -f docker-compose.prod.yml exec -T web printenv ALLOWED_HOSTS"


& ssh -i $SshKey -o ConnectTimeout=15 $Target $RemoteCommand

if ($LASTEXITCODE -ne 0) {
    throw "EC2 update failed. Local .env has not been changed."
}

# 5. Update local Windows .env
$UpdatedEnv = [regex]::Replace(
    $EnvText,
    '(?m)^ALLOWED_HOSTS=.*$',
    "ALLOWED_HOSTS=$AllowedHostsString"
)

[System.IO.File]::WriteAllText(
    $EnvFile,
    $UpdatedEnv,
    [System.Text.UTF8Encoding]::new($false)
)

Write-Host "`n--------------------------------" -ForegroundColor Green
Write-Host "LogShift IP update successful!" -ForegroundColor Green
Write-Host "Public IP:  $PublicIp"
Write-Host "Private IP: $PrivateIp"
Write-Host "Local and remote .env updated."
Write-Host "Web container recreated."
Write-Host "--------------------------------" -ForegroundColor Green