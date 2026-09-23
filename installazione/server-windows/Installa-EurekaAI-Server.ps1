#Requires -Version 5.1
<#
.SYNOPSIS
  Pacchetto autoinstallante Eureka AI su Windows Server (Python + Waitress + Servy).

.DESCRIPTION
  1. (Opzionale) Copia/estrae i file in -InstallRoot
  2. Crea venv e installa dipendenze (prod_install; Python via winget se mancante)
  3. Installa Servy (winget) se mancante
  4. Registra e avvia il servizio Windows con servy-cli

  Eseguire come Amministratore, oppure lasciare che lo script si rilanzi elevato.

.EXAMPLE
  .\Installa-EurekaAI-Server.ps1
  .\Installa-EurekaAI-Server.ps1 -InstallRoot "C:\Eureka_AI" -Port 8000 -InstallServy -InstallPython
#>

param(
    [string]$InstallRoot = "C:\Eureka_AI",
    [string]$ServiceName = "EurekaAI",
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Threads = 6,
    [switch]$InstallServy,
    [switch]$InstallPython,
    [switch]$SkipCopy,
    [switch]$SkipService,
    [switch]$NoElevate
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Get-PackageRoot {
    # Script in root progetto (dopo unzip) oppure in installazione\server-windows\.
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
        "-ListenHost", "`"$ListenHost`"",
        "-Port", "$Port",
        "-Threads", "$Threads",
        "-NoElevate"
    )
    if ($InstallServy) { $argList += "-InstallServy" }
    if ($InstallPython) { $argList += "-InstallPython" }
    if ($SkipCopy) { $argList += "-SkipCopy" }
    if ($SkipService) { $argList += "-SkipService" }
    $p = Start-Process -FilePath "powershell.exe" -Verb RunAs -ArgumentList $argList -Wait -PassThru
    exit $p.ExitCode
}

if (-not (Test-IsAdmin)) {
    Write-Error "Servono privilegi di Amministratore."
}

$SourceRoot = Get-PackageRoot
Write-Host "Sorgente pacchetto: $SourceRoot"
Write-Host "Destinazione:       $InstallRoot"

if (-not $SkipCopy) {
    if ($SourceRoot -ne $InstallRoot) {
        Write-Host "Copia file applicazione..."
        New-Item -ItemType Directory -Force -Path $InstallRoot | Out-Null
        $excludeDirs = @(
            ".git", ".venv", "node_modules", "__pycache__", ".cursor",
            "staticfiles", "logs", "installazione\dist", "htmlcov", ".pytest_cache"
        )
        $robocopyArgs = @(
            $SourceRoot, $InstallRoot, "/E", "/XD"
        ) + $excludeDirs + @(
            "/XF", "*.pyc", "*.pyo", ".env",
            "/NFL", "/NDL", "/NJH", "/NJS", "/nc", "/ns", "/np"
        )
        & robocopy @robocopyArgs | Out-Null
        # robocopy exit 0-7 = success
        if ($LASTEXITCODE -ge 8) {
            Write-Error "robocopy fallito (exit $LASTEXITCODE)."
        }
        # Non sovrascrivere .env esistente sul server
        $dstEnv = Join-Path $InstallRoot ".env"
        $srcExample = Join-Path $SourceRoot ".env.example"
        if (-not (Test-Path $dstEnv) -and (Test-Path $srcExample)) {
            Copy-Item $srcExample $dstEnv
            Write-Warning "Creato $dstEnv da .env.example - CONFIGURARE prima dell'uso (SECRET_KEY, DB, DEBUG=False)."
        }
    } else {
        Write-Host "Sorgente = destinazione: salto copia."
    }
}

Set-Location $InstallRoot

$prodInstall = Join-Path $InstallRoot "scripts\prod_install.ps1"
if (-not (Test-Path $prodInstall)) {
    Write-Error "Manca $prodInstall"
}
Write-Host "=== prod_install ==="
$prodArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $prodInstall)
if ($InstallPython) { $prodArgs += "-InstallPythonIfMissing" }
& powershell.exe @prodArgs
if ($LASTEXITCODE -ne 0) { Write-Error "prod_install fallito." }

if ($SkipService) {
    Write-Host "SkipService: installazione file completata. Avvio manuale: .\scripts\prod_start.ps1"
    exit 0
}

$svcScript = Join-Path $InstallRoot "scripts\install_service_servy.ps1"
$svcArgs = @{
    ServiceName = $ServiceName
    ListenHost  = $ListenHost
    Port        = $Port
    Threads     = $Threads
}
if ($InstallServy) { $svcArgs["InstallServyIfMissing"] = $true }

Write-Host "=== install_service_servy ==="
& $svcScript @svcArgs
if ($LASTEXITCODE -ne 0) { Write-Error "Installazione servizio fallita." }

Write-Host ""
Write-Host "========================================"
Write-Host " Eureka AI installato"
Write-Host " Path:     $InstallRoot"
Write-Host " Servizio: $ServiceName"
Write-Host " URL:      http://127.0.0.1:$Port/"
Write-Host "========================================"
Write-Host "Verifica .env (DEBUG=False, ALLOWED_HOSTS, DATABASE_URL, SECRET_KEY)."
Write-Host "Documentazione Servy: installazione\server-windows\LEGGIMI-SERVY.md"
