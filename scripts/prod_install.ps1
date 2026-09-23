# Eureka AI - preparazione ambiente produzione (Windows Server)
# Uso (dalla root del progetto):
#   .\scripts\prod_install.ps1
#   .\scripts\prod_install.ps1 -InstallPythonIfMissing
#
# Richiede: Python 3.11+ (py launcher, python nel PATH, oppure installabile via winget).

param(
    [switch]$SkipMigrate,
    [switch]$SkipCollectStatic,
    [switch]$InstallPythonIfMissing
)

$ErrorActionPreference = "Stop"

if ($PSScriptRoot) {
    $Root = Split-Path -Parent $PSScriptRoot
} else {
    $Root = (Get-Location).Path
}
Set-Location $Root
Write-Host "Cartella progetto: $Root"

function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Get-PythonFromCommand {
    param([string]$CommandName, [string[]]$Args)
    $cmd = Get-Command $CommandName -ErrorAction SilentlyContinue
    if (-not $cmd) { return $null }
    try {
        $exe = & $CommandName @Args 2>$null
        if ($exe) {
            $exe = ($exe | Select-Object -First 1).ToString().Trim()
            if ($exe -and (Test-Path -LiteralPath $exe)) { return $exe }
        }
    } catch { }
    return $null
}

function Find-SystemPython {
    Update-SessionPath

    $fromPy = Get-PythonFromCommand -CommandName "py" -Args @("-3", "-c", "import sys; print(sys.executable)")
    if ($fromPy) { return $fromPy }

    $fromPython = Get-PythonFromCommand -CommandName "python" -Args @("-c", "import sys; print(sys.executable)")
    if ($fromPython) { return $fromPython }

    $roots = @(
        $env:LOCALAPPDATA,
        ${env:ProgramFiles},
        ${env:ProgramFiles(x86)}
    ) | Where-Object { $_ }

    $patterns = @(
        "Programs\Python\Python3*\python.exe",
        "Python3*\python.exe",
        "Python\Python3*\python.exe"
    )

    $found = @()
    foreach ($root in $roots) {
        foreach ($pat in $patterns) {
            $found += Get-ChildItem -Path (Join-Path $root $pat) -ErrorAction SilentlyContinue
        }
    }

    $best = $found |
        Where-Object { $_.FullName -notmatch '\\WindowsApps\\' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1

    if ($best) { return $best.FullName }
    return $null
}

function Install-PythonViaWinget {
    Write-Host "Installazione Python 3.12 via winget..."
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Error @"
winget non disponibile e Python non trovato.
Installa Python 3.11+ da https://www.python.org/downloads/windows/
(spunta 'Add python.exe to PATH'), poi riesegui Installa.cmd
"@
    }
    & winget install --id Python.Python.3.12 -e --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        Write-Warning "winget Python.Python.3.12 exit $LASTEXITCODE - provo Python.Python.3.11"
        & winget install --id Python.Python.3.11 -e --accept-package-agreements --accept-source-agreements --silent
    }
    Update-SessionPath
    Start-Sleep -Seconds 2
}

$SystemPython = Find-SystemPython
if (-not $SystemPython) {
    if ($InstallPythonIfMissing) {
        Install-PythonViaWinget
        $SystemPython = Find-SystemPython
    }
    if (-not $SystemPython) {
        Write-Error @"
Python non trovato. Installa Python 3.11+ (opzione 'Add python.exe to PATH') e riprova.
Download: https://www.python.org/downloads/windows/
Oppure riesegui con: .\scripts\prod_install.ps1 -InstallPythonIfMissing
"@
    }
}

Write-Host "Python: $SystemPython"
& $SystemPython -c "import sys; assert sys.version_info >= (3, 11), sys.version"
if ($LASTEXITCODE -ne 0) {
    Write-Error "Serve Python 3.11 o superiore."
}

$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Host "Creo virtualenv .venv ..."
    & $SystemPython -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { Write-Error "Creazione venv fallita." }
}

$EnvFile = Join-Path $Root ".env"
$EnvExample = Join-Path $Root ".env.example"
if (-not (Test-Path -LiteralPath $EnvFile)) {
    if (Test-Path -LiteralPath $EnvExample) {
        Copy-Item $EnvExample $EnvFile
        Write-Warning "Creato .env da .env.example - configuralo prima di andare in produzione (SECRET_KEY, DATABASE_URL, ALLOWED_HOSTS, DEBUG=False)."
    } else {
        Write-Error "Manca .env (e .env.example)."
    }
}

Write-Host "Aggiorno pip / dipendenze..."
& $VenvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Write-Error "pip upgrade fallito." }
& $VenvPython -m pip install -r (Join-Path $Root "requirements.txt")
if ($LASTEXITCODE -ne 0) { Write-Error "Installazione requirements fallita." }

if (Test-Path (Join-Path $Root "package.json")) {
    if (Get-Command npm -ErrorAction SilentlyContinue) {
        Write-Host "npm install (static vendor)..."
        & npm install --omit=dev
    } else {
        Write-Warning "npm non trovato: salta static/vendor. Esegui npm install se i CSS/JS Tabler mancano."
    }
}

$env:DJANGO_SETTINGS_MODULE = "config.settings"

if (-not $SkipMigrate) {
    Write-Host "migrate..."
    & $VenvPython manage.py migrate --noinput
    if ($LASTEXITCODE -ne 0) {
        Write-Host ""
        Write-Host "ERRORE: migrate non riesce a connettersi al database." -ForegroundColor Red
        Write-Host "1) Apri e configura: $EnvFile"
        Write-Host "   DATABASE_URL=postgres://USER:PASSWORD@HOST:5432/NOME_DB"
        Write-Host "2) Verifica che PostgreSQL sia avviato e raggiungibile da questo server."
        Write-Host "3) Poi riesegui:"
        Write-Host "   cd C:\Eureka_AI"
        Write-Host "   .\scripts\prod_install.ps1"
        Write-Host "   oppure solo: .\.venv\Scripts\python.exe manage.py migrate"
        Write-Host ""
        Write-Error "migrate fallito (connessione database)."
    }
}

if (-not $SkipCollectStatic) {
    Write-Host "collectstatic..."
    & $VenvPython manage.py collectstatic --noinput
    if ($LASTEXITCODE -ne 0) { Write-Error "collectstatic fallito." }
}

New-Item -ItemType Directory -Force -Path (Join-Path $Root "logs") | Out-Null

Write-Host ""
Write-Host "Installazione OK."
Write-Host "  Avvio manuale:  .\scripts\prod_start.ps1"
Write-Host "  Servizio Servy: .\scripts\install_service_servy.ps1  (PowerShell Amministratore)"
