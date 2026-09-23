# Installa PostgreSQL su Windows (se mancante) e crea DB/utente per Eureka AI.
# Eseguire come Amministratore:
#   .\scripts\install_postgresql_windows.ps1
#   .\scripts\install_postgresql_windows.ps1 -DbPassword "MiaPasswordSicura"
#
# Poi in C:\Eureka_AI\.env:
#   DATABASE_URL=postgres://eureka:MiaPasswordSicura@127.0.0.1:5432/eureka_ai

param(
    [string]$DbName = "eureka_ai",
    [string]$DbUser = "eureka",
    [string]$DbPassword = "eureka",
    [int]$Port = 5432,
    [switch]$SkipInstall,
    [switch]$SkipCreateDb
)

$ErrorActionPreference = "Stop"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Update-SessionPath {
    $machine = [System.Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [System.Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Find-Psql {
    Update-SessionPath
    $cmd = Get-Command psql -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $found = Get-ChildItem -Path "${env:ProgramFiles}\PostgreSQL\*\bin\psql.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending |
        Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

if (-not (Test-IsAdmin)) {
    Write-Error "Esegui PowerShell come Amministratore."
}

$psql = Find-Psql

if (-not $psql -and -not $SkipInstall) {
    Write-Host "PostgreSQL non trovato."
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Write-Host "Installazione PostgreSQL via winget (puo richiedere alcuni minuti)..."
        & winget install --id PostgreSQL.PostgreSQL -e --accept-package-agreements --accept-source-agreements
        Update-SessionPath
        $psql = Find-Psql
    }
    if (-not $psql) {
        Write-Host ""
        Write-Host "winget non disponibile o installazione automatica non riuscita."
        Write-Host "Installa PostgreSQL manualmente:"
        Write-Host "  1) Scarica: https://www.postgresql.org/download/windows/"
        Write-Host "     (installer EDB / EnterpriseDB)"
        Write-Host "  2) Durante setup:"
        Write-Host "     - porta $Port"
        Write-Host "     - imposta password per utente 'postgres' (annotarla)"
        Write-Host "     - lascia selezionati strumenti a riga di comando (bin)"
        Write-Host "  3) Chiudi e riapri questo prompt Admin, poi riesegui:"
        Write-Host "     .\scripts\install_postgresql_windows.ps1 -SkipInstall"
        Write-Host ""
        Write-Error "PostgreSQL non installato."
    }
}

if (-not $psql) {
    Write-Error "psql.exe non trovato. Aggiungi ...\PostgreSQL\<ver>\bin al PATH e riprova."
}

Write-Host "psql: $psql"

if (-not $SkipCreateDb) {
    Write-Host "Creazione ruolo/database (ti verra chiesta la password di 'postgres')..."
    $env:PGPASSWORD = $null

    $sql = @"
DO `$`$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$DbUser') THEN
    CREATE ROLE $DbUser LOGIN PASSWORD '$DbPassword';
  ELSE
    ALTER ROLE $DbUser WITH LOGIN PASSWORD '$DbPassword';
  END IF;
END
`$`$;
SELECT 'ok_role' AS status;
"@

    # Crea ruolo (connessione come postgres al DB default)
    $sql | & $psql -U postgres -h 127.0.0.1 -p $Port -d postgres -v ON_ERROR_STOP=1
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Creazione ruolo fallita. Verifica password di 'postgres' e che il servizio PostgreSQL sia avviato."
    }

    $exists = & $psql -U postgres -h 127.0.0.1 -p $Port -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$DbName'"
    if ($exists -notmatch "1") {
        & $psql -U postgres -h 127.0.0.1 -p $Port -d postgres -v ON_ERROR_STOP=1 `
            -c "CREATE DATABASE $DbName OWNER $DbUser ENCODING 'UTF8';"
        if ($LASTEXITCODE -ne 0) { Write-Error "Creazione database fallita." }
    } else {
        Write-Host "Database '$DbName' gia presente."
        & $psql -U postgres -h 127.0.0.1 -p $Port -d postgres -c "ALTER DATABASE $DbName OWNER TO $DbUser;" | Out-Null
    }

    Write-Host ""
    Write-Host "Database pronto."
    Write-Host "Imposta in .env:"
    Write-Host "  DATABASE_URL=postgres://${DbUser}:${DbPassword}@127.0.0.1:${Port}/${DbName}"
    Write-Host ""
    Write-Host "Poi:"
    Write-Host "  cd C:\Eureka_AI"
    Write-Host "  .\scripts\prod_install.ps1"
    Write-Host "  .\scripts\install_service_servy.ps1 -InstallServyIfMissing"
}
