param(
    [string]$ProjectDirectory = (Resolve-Path "$PSScriptRoot\..\.."),
    [string]$Destination = "$PSScriptRoot\..\..\backups",
    [string]$DatabaseUser = "schoolerp",
    [string]$DatabaseName = "schoolerp"
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectDirectory
New-Item -ItemType Directory -Path $Destination -Force | Out-Null

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$fileName = "schoolerp-$timestamp.dump"
$containerPath = "/tmp/$fileName"
$outputPath = Join-Path (Resolve-Path $Destination) $fileName
$composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.local-db.yml")

docker compose @composeFiles exec -T db pg_dump -U $DatabaseUser -d $DatabaseName -Fc -f $containerPath
docker compose @composeFiles cp "db:$containerPath" $outputPath
docker compose @composeFiles exec -T db sh -c "rm -f '$containerPath'"

$hash = Get-FileHash -Algorithm SHA256 $outputPath
Write-Host "Backup created: $outputPath"
Write-Host "SHA256: $($hash.Hash)"
