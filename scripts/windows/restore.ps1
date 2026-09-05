param(
    [Parameter(Mandatory = $true)]
    [string]$BackupFile,
    [Parameter(Mandatory = $true)]
    [switch]$ConfirmRestore,
    [string]$ProjectDirectory = (Resolve-Path "$PSScriptRoot\..\.."),
    [string]$DatabaseUser = "schoolerp",
    [string]$DatabaseName = "schoolerp"
)

$ErrorActionPreference = "Stop"
if (-not $ConfirmRestore) {
    throw "Restore was not confirmed. Re-run with -ConfirmRestore."
}
if (-not (Test-Path $BackupFile -PathType Leaf)) {
    throw "Backup file does not exist: $BackupFile"
}

Set-Location $ProjectDirectory
Write-Host "Creating a safety backup before restore..."
& "$PSScriptRoot\backup.ps1" -ProjectDirectory $ProjectDirectory -DatabaseUser $DatabaseUser -DatabaseName $DatabaseName

$safeName = [IO.Path]::GetFileName($BackupFile)
if ($safeName -notmatch "^[A-Za-z0-9._-]+$") {
    throw "Backup filename may contain only letters, numbers, dot, underscore and hyphen."
}
$containerPath = "/tmp/$safeName"
$composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.local-db.yml")

docker compose @composeFiles stop backend
try {
    docker compose @composeFiles cp $BackupFile "db:$containerPath"
    docker compose @composeFiles exec -T db pg_restore -U $DatabaseUser -d $DatabaseName --clean --if-exists --no-owner $containerPath
    docker compose @composeFiles exec -T db sh -c "rm -f '$containerPath'"
}
finally {
    docker compose @composeFiles start backend
}

Write-Host "Restore completed. Verify application health and audit recent records."
