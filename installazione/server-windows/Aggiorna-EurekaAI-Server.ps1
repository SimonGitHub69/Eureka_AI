#Requires -Version 5.1
<#
.SYNOPSIS
  Aggiorna un'installazione Eureka AI esistente (codice + migrate + static + restart Servy).

.DESCRIPTION
  Copia i file dal pacchetto/sorgente in -InstallRoot senza sovrascrivere .env e .venv.
  Poi: migrate, collectstatic, restart servizio.

.EXAMPLE
  .\Aggiorna-EurekaAI-Server.ps1
  .\Aggiorna-EurekaAI-Server.ps1 -InstallRoot "C:\Eureka_AI"
#>

param(
    [string]$InstallRoot = "C:\Eureka_AI",
    [string]$ServiceName = "EurekaAI",
    [switch]$SkipRestart,
    [switch]$SkipNpm,
    [switch]$NoElevate
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PackageRoot {
    if ($PSScriptRoot) {
        $here = $PSScriptRoot
    } else {
        $here = (Get-Location).Path
    }
    foreach ($candidate in @(
        $here,
        (Split-Path -Parent $here),
        (Split-Path -Parent (Split-Path -Parent $here))
    )) {
        if ($candidate -and (Test-Path (Join-Path $candidate "manage.py"))) {
            return $candidate
        }
    }
    Write-Error "Impossibile individuare la root Eureka AI (manage.py)."
}

if (-not $NoElevate -and -not (Test-IsAdmin)) {
    Write-Host "Rilancio come Amministratore..."
    $argList = @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "`"$PSCommandPath`"",
        "-InstallRoot", "`"$InstallRoot`"",
        "-ServiceName", "`"$ServiceName`"",
        "-NoElevate"
    )
    if ($SkipRestart) { $argList += "-SkipRestart" }
    if ($SkipNpm) { $argList += "-SkipNpm" }
    $p = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList -Wait -PassThru
    exit $p.ExitCode
}

$SourceRoot = Get-PackageRoot
Write-Host "Sorgente:     $SourceRoot"
Write-Host "Destinazione: $InstallRoot"

if (-not (Test-Path (Join-Path $InstallRoot "manage.py"))) {
    Write-Error "Installazione non trovata in $InstallRoot. Usa prima Installa.cmd."
}

if ($SourceRoot -ne $InstallRoot) {
    Write-Host "Copia file (esclusi .env .venv logs staticfiles)..."
    $excludeDirs = @(
        ".git", ".venv", "node_modules", "__pycache__", ".cursor",
        "staticfiles", "logs", "installazione\dist", "htmlcov", ".pytest_cache"
    )
    $robocopyArgs = @($SourceRoot, $InstallRoot, "/E", "/XD") + $excludeDirs + @(
        "/XF", "*.pyc", "*.pyo", ".env",
        "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
    )
    & robocopy @robocopyArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        Write-Error "robocopy fallito (exit $LASTEXITCODE)."
    }
} else {
    Write-Host "Sorgente = destinazione: salto copia."
}

Set-Location $InstallRoot
$VenvPython = Join-Path $InstallRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Error "Manca .venv. Esegui prima Installa.cmd / prod_install.ps1"
}

Write-Host "=== pip install -r requirements.txt ==="
& $VenvPython -m pip install -r (Join-Path $InstallRoot "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Error "pip install fallito." }

if (-not $SkipNpm -and (Test-Path (Join-Path $InstallRoot "package.json"))) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "=== npm install ==="
        & npm install --omit=dev
    } else {
        Write-Warning "npm non trovato: salto static/vendor."
    }
}

$env:DJANGO_SETTINGS_MODULE = "config.settings"
Write-Host "=== migrate ==="
& $VenvPython manage.py migrate --noinput
if ($LASTEXITCODE -ne 0) { Write-Error "migrate fallito." }

Write-Host "=== collectstatic ==="
& $VenvPython manage.py collectstatic --noinput
if ($LASTEXITCODE -ne 0) { Write-Error "collectstatic fallito." }

if (-not $SkipRestart) {
    $servy = Join-Path $env:ProgramFiles "Servy\servy-cli.exe"
    if (Test-Path $servy) {
        Write-Host "=== restart $ServiceName ==="
        & $servy restart --name=$ServiceName
        & $servy status --name=$ServiceName
    } else {
        Write-Warning "servy-cli non trovato. Riavvia manualmente: Restart-Service $ServiceName"
        Restart-Service $ServiceName -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Aggiornamento completato: $InstallRoot"
