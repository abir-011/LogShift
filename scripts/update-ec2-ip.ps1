
# LogShift - Automatic EC2 Public IP Updater

$Region = "ap-southeast-2"
$EnvFile = Join-Path $PSScriptRoot "..\.env"

# Read EC2 Instance ID from local .env
$InstanceLine = Get-Content $EnvFile |
    Where-Object { $_ -match '^EC2_INSTANCE_ID=' }

if (-not $InstanceLine) {
    Write-Host "EC2_INSTANCE_ID not found in .env" -ForegroundColor Red
    exit 1
}

$InstanceId = ($InstanceLine -split '=', 2)[1].Trim()

Write-Host "Fetching LogShift EC2 public IP..." -ForegroundColor Cyan

# Retrieve current public IP
$PublicIp = aws ec2 describe-instances `
    --region $Region `
    --instance-ids $InstanceId `
    --query "Reservations[0].Instances[0].PublicIpAddress" `
    --output text

if ($LASTEXITCODE -ne 0 -or
    [string]::IsNullOrWhiteSpace($PublicIp) -or
    $PublicIp -eq "None") {
    Write-Host "Could not retrieve public IP. Is EC2 running?" -ForegroundColor Red
    exit 1
}

# Update only ALLOWED_HOSTS
$Content = Get-Content $EnvFile

$UpdatedContent = $Content -replace `
    '^ALLOWED_HOSTS=.*$', `
    "ALLOWED_HOSTS=$PublicIp,localhost,127.0.0.1"

$UpdatedContent | Set-Content $EnvFile

Write-Host "Successfully updated ALLOWED_HOSTS!" -ForegroundColor Green
Write-Host "New EC2 public IP: $PublicIp"
