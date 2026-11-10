
# LogShift - Automatic EC2 Public IP Updater

$Region = "ap-southeast-2"
$InstanceId = "i-0a5fb35c151a5e0df"  # Replace with your actual EC2 instance ID
$EnvFile = Join-Path $PSScriptRoot "..\.env"

Write-Host "Fetching LogShift EC2 public IP..." -ForegroundColor Cyan

# Retrieve the current public IP
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

# Read the existing .env file
$Content = Get-Content $EnvFile

# Update only ALLOWED_HOSTS
$UpdatedContent = $Content -replace `
    '^ALLOWED_HOSTS=.*$', `
    "ALLOWED_HOSTS=$PublicIp,localhost,127.0.0.1"

# Save the updated .env file
$UpdatedContent | Set-Content $EnvFile

Write-Host "Successfully updated ALLOWED_HOSTS!" -ForegroundColor Green
Write-Host "New EC2 public IP: $PublicIp"
