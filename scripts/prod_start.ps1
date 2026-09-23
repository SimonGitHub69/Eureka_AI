# Avvia Eureka AI con Waitress (produzione, console).
# Esempio: .\scripts\prod_start.ps1
#          .\scripts\prod_start.ps1 -ListenHost 0.0.0.0 -Port 8000

param(
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Threads = 6
)

$ErrorActionPreference = "Stop"
if ($PSScriptRoot) {
    $Root = Split-Path -Parent $PSScriptRoot
} else {
    $Root = (Get-Location).Path
}
Set-Location $Root
Write-Host "Cartella progetto: $Root"

$Python = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    Write-Error "Virtualenv non trovato: $Python - esegui .\scripts\prod_install.ps1"
}

if (-not (Test-Path (Join-Path $Root ".env"))) {
    Write-Error "Manca .env in $Root"
}

$env:DJANGO_SETTINGS_MODULE = "config.settings"
$Listen = "{0}:{1}" -f $ListenHost, $Port
Write-Host ("Eureka AI in ascolto su http://{0}/" -f $Listen)
& $Python -m waitress --listen=$Listen --threads=$Threads config.wsgi:application
