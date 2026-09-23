# Installa/aggiorna Eureka AI come servizio Windows tramite Servy CLI.
# Eseguire come Amministratore:
#   .\scripts\install_service_servy.ps1
#   .\scripts\install_service_servy.ps1 -Port 8000 -ServiceName EurekaAI
#
# Documentazione Servy:
#   https://github.com/aelassas/servy/wiki/Servy-CLI
#   https://github.com/aelassas/servy/wiki/Installation-Guide

param(
    [string]$ServiceName = "EurekaAI",
    [string]$DisplayName = "Eureka AI",
    [string]$ListenHost = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Threads = 6,
    [string]$StartupType = "Automatic",
    [switch]$SkipFirewall,
    [switch]$SkipStart,
    [switch]$InstallServyIfMissing
)

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
        Write-Error "Esegui PowerShell come Amministratore."
    }
}

function Resolve-ServyCli {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Servy\servy-cli.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Servy\servy-cli.exe")
    )
    foreach ($p in $candidates) {
        if ($p -and (Test-Path $p)) { return $p }
    }
    $cmd = Get-Command servy-cli -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    return $null
}

function Install-ServyViaWinget {
    Write-Host "Installazione Servy via winget..."
    & winget install --id aelassas.Servy -e --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        # -1978335189 = already installed (varies by winget version)
        Write-Warning "winget exit code: $LASTEXITCODE - verifico comunque servy-cli."
    }
}

function Install-ServyFromGitHub {
    Write-Host "Download Servy da GitHub Releases..."
    $api = "https://api.github.com/repos/aelassas/servy/releases/latest"
    try {
        $release = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "EurekaAI-Installer" }
    } catch {
        Write-Error "Impossibile leggere GitHub Releases. Scarica manualmente: https://github.com/aelassas/servy/releases"
    }
    $asset = $release.assets |
        Where-Object { $_.name -match 'x64.*installer\.exe$|installer-x64\.exe$|servy-.*-x64-installer\.exe$' } |
        Select-Object -First 1
    if (-not $asset) {
        $asset = $release.assets |
            Where-Object { $_.name -like "*.exe" -and $_.name -match "install" } |
            Select-Object -First 1
    }
    if (-not $asset) {
        Write-Error "Nessun installer trovato nella release. Apri: https://github.com/aelassas/servy/releases"
    }
    $tmp = Join-Path $env:TEMP $asset.name
    Write-Host "Scarico $($asset.name) ..."
    Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $tmp -UseBasicParsing
    Write-Host "Installazione silenziosa Servy..."
    $p = Start-Process -FilePath $tmp -ArgumentList "/VERYSILENT","/NORESTART","/SUPPRESSMSGBOXES","/SP-","/CLOSEAPPLICATIONS" -Wait -PassThru
    if ($p.ExitCode -ne 0) {
        Write-Warning "Installer exit $($p.ExitCode) - verifico comunque servy-cli."
    }
    # Aggiorna PATH sessione
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Install-ServyIfNeeded {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        try {
            Install-ServyViaWinget
            return
        } catch {
            Write-Warning "winget fallito: $($_.Exception.Message) - provo download GitHub."
        }
    } else {
        Write-Host "winget non disponibile - uso download GitHub."
    }
    Install-ServyFromGitHub
}

Assert-Admin

if ($PSScriptRoot) {
    $Root = Split-Path -Parent $PSScriptRoot
} else {
    $Root = (Get-Location).Path
}

$Python = Join-Path $Root ".venv\Scripts\python.exe"
$EnvFile = Join-Path $Root ".env"
$LogsDir = Join-Path $Root "logs"

if (-not (Test-Path $Python)) {
    Write-Error "Virtualenv non trovato: $Python - esegui prima .\scripts\prod_install.ps1"
}
if (-not (Test-Path $EnvFile)) {
    Write-Error "Manca .env in $Root"
}

New-Item -ItemType Directory -Force -Path $LogsDir | Out-Null

$ServyCli = Resolve-ServyCli
if (-not $ServyCli) {
    if ($InstallServyIfMissing) {
        Install-ServyIfNeeded
        $ServyCli = Resolve-ServyCli
    }
    if (-not $ServyCli) {
        Write-Error @"
servy-cli non trovato.
Installa Servy (come Admin):
  1) Scarica l'installer da https://github.com/aelassas/servy/releases
  2) Esegui l'installer (x64)
  3) Riesegui: .\scripts\install_service_servy.ps1
Oppure: .\scripts\install_service_servy.ps1 -InstallServyIfMissing
"@
    }
}

Write-Host "Servy CLI: $ServyCli"
& $ServyCli --version --quiet 2>$null
if ($LASTEXITCODE -ne 0) {
    & $ServyCli version
}

# Parametri e env via variabili Servy (non restano in chiaro nella lista processi di install).
$ProcessParams = "-m waitress --listen=${ListenHost}:${Port} --threads=$Threads config.wsgi:application"
$EnvVars = "DJANGO_SETTINGS_MODULE=config.settings"

$StdoutLog = Join-Path $LogsDir "waitress.out.log"
$StderrLog = Join-Path $LogsDir "waitress.err.log"

Write-Host "Registrazione servizio '$ServiceName' (install idempotente)..."
$env:SERVY_PROCESS_PARAMETERS = $ProcessParams
$env:SERVY_ENVIRONMENT_VARIABLES = $EnvVars
try {
    & $ServyCli install `
        --quiet `
        --name=$ServiceName `
        --displayName=$DisplayName `
        --description="Eureka AI (Django + Waitress) - gestionale web" `
        --path=$Python `
        --startupDir=$Root `
        --startupType=$StartupType `
        --stdout=$StdoutLog `
        --stderr=$StderrLog `
        --enableSizeRotation `
        --rotationSize=10 `
        --maxRotations=12 `
        --recoveryAction=RestartService `
        --maxRestartAttempts=5 `
        --startTimeout=60 `
        --stopTimeout=30
    if ($LASTEXITCODE -ne 0) {
        Write-Error "servy-cli install fallito (exit $LASTEXITCODE)."
    }
} finally {
    Remove-Item Env:SERVY_PROCESS_PARAMETERS -ErrorAction SilentlyContinue
    Remove-Item Env:SERVY_ENVIRONMENT_VARIABLES -ErrorAction SilentlyContinue
}

if (-not $SkipFirewall) {
    $ruleName = "Eureka AI HTTP $Port"
    $rule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
    if (-not $rule) {
        New-NetFirewallRule -DisplayName $ruleName -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port | Out-Null
        Write-Host "Regola firewall creata: TCP $Port"
    } else {
        Write-Host "Regola firewall gia presente: $ruleName"
    }
}

if (-not $SkipStart) {
    Write-Host "Avvio servizio..."
    & $ServyCli start --quiet --name=$ServiceName
    Start-Sleep -Seconds 2
    & $ServyCli status --name=$ServiceName
}

Write-Host ""
Write-Host "Servizio: $ServiceName"
Write-Host "URL:      http://127.0.0.1:${Port}/"
Write-Host "Log:      $LogsDir"
Write-Host ""
Write-Host "Comandi Servy utili:"
Write-Host "  servy-cli status  --name=$ServiceName"
Write-Host "  servy-cli start   --name=$ServiceName"
Write-Host "  servy-cli stop    --name=$ServiceName"
Write-Host "  servy-cli restart --name=$ServiceName"
Write-Host "  .\scripts\uninstall_service_servy.ps1"
Write-Host ""
Write-Host "Oppure da services.msc / sc.exe start $ServiceName"
