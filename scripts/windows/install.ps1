param(
    [string]$ProjectDirectory = (Resolve-Path "$PSScriptRoot\..\.."),
    [switch]$UseLanTls
)

$ErrorActionPreference = "Stop"
Set-Location $ProjectDirectory

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker is not installed or is not available in PATH."
}

docker compose version | Out-Null

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    throw "Created .env from .env.example. Set unique SECRET_KEY, POSTGRES_PASSWORD and SUPER_ADMIN_PASSWORD, then run this script again."
}

$envText = Get-Content ".env" -Raw
$unsafeValues = @(
    "change-this-to-a-long-random-string-in-production-min-32-chars",
    "change-this-local-database-password",
    "ChangeMeImmediately123!"
)
foreach ($unsafeValue in $unsafeValues) {
    if ($envText.Contains($unsafeValue)) {
        throw ".env still contains an unsafe default value: $unsafeValue"
    }
}
if ($envText -notmatch "(?m)^APP_ENV=(production|prod)\s*$") {
    throw ".env must set APP_ENV=production for a school-server installation."
}
if ($envText -match "(?m)^DEBUG=true\s*$") {
    throw ".env must set DEBUG=false for a school-server installation."
}

$composeFiles = @("-f", "docker-compose.yml", "-f", "docker-compose.local-db.yml")
if ($UseLanTls) {
    if (-not (Test-Path "certs\schoolerp.crt") -or -not (Test-Path "certs\schoolerp.key")) {
        throw "LAN TLS requires certs\schoolerp.crt and certs\schoolerp.key. See docs\WINDOWS_LAN_DEPLOY.md."
    }
    $composeFiles += @("-f", "docker-compose.lan-tls.yml")
}

docker compose @composeFiles config --quiet
docker compose @composeFiles up --build -d --remove-orphans
docker compose @composeFiles ps

Write-Host "School ERP started. Verify http://localhost/health (or https://localhost/health with LAN TLS)."
