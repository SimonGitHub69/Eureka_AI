# Costruisce lo ZIP server Mac autoinstallante.
# Imposta bit Unix eseguibili su .command / .sh (anche se generato su Windows).
#
# Uso (dalla root progetto):
#   .\installazione\server-mac\Build-MacServerPackage.ps1

param(
    [string]$Version = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$ServerMacDir = $PSScriptRoot
$InstallazioneDir = Split-Path -Parent $ServerMacDir
$Root = Split-Path -Parent $InstallazioneDir

if (-not $Version) {
    $pkg = Join-Path $Root "package.json"
    if (Test-Path $pkg) {
        $Version = (Get-Content $pkg -Raw | ConvertFrom-Json).version
    }
    if (-not $Version) { $Version = "1.0.0" }
}

if (-not $OutDir) {
    $OutDir = Join-Path $InstallazioneDir "dist"
}
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Stage = Join-Path $env:TEMP ("EurekaAI_ServerMac_stage_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Write-Host "Staging da $Root -> $Stage"

$excludeDirNames = @(
    ".git", ".venv", "node_modules", "__pycache__", ".cursor",
    "staticfiles", "logs", "htmlcov", ".pytest_cache",
    "agent-transcripts", "agent-tools"
)
# Nota: NON escludere "dist" in /XD — Tabler/ApexCharts vivono in .../libs/*/dist/
# e senza apexcharts.min.js i grafici sul server cliente restano vuoti.

Get-ChildItem -Path $Root -Force | ForEach-Object {
    $name = $_.Name
    if ($excludeDirNames -contains $name) { return }
    if ($name -eq "installazione") {
        $destInst = Join-Path $Stage "installazione\server-mac"
        New-Item -ItemType Directory -Force -Path $destInst | Out-Null
        Copy-Item -Path (Join-Path $ServerMacDir "*") -Destination $destInst -Recurse -Force
        return
    }
    $dest = Join-Path $Stage $name
    if ($_.PSIsContainer) {
        & robocopy $_.FullName $dest /E /XD $excludeDirNames /XF *.pyc *.pyo .env /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
        if ($LASTEXITCODE -ge 8) { Write-Error "robocopy fallito su $name" }
    } else {
        if ($name -eq ".env") { return }
        Copy-Item $_.FullName $dest -Force
    }
}

# Entry point comodi in root dello stage
$utf8 = New-Object System.Text.UTF8Encoding $false
function Write-LfFile([string]$Src, [string]$Dst) {
    $raw = [System.IO.File]::ReadAllText($Src)
    $raw = $raw -replace "`r`n", "`n" -replace "`r", "`n"
    [System.IO.File]::WriteAllText($Dst, $raw, $utf8)
}

$cmdSrc = Join-Path $ServerMacDir "Installa-Eureka-Mac-Server.command"
Write-LfFile $cmdSrc (Join-Path $Stage "Installa-Eureka-Mac-Server.command")
# Anche sotto installazione/server-mac (gia copiato): normalizza LF
Write-LfFile $cmdSrc (Join-Path $Stage "installazione\server-mac\Installa-Eureka-Mac-Server.command")

Copy-Item (Join-Path $ServerMacDir "LEGGIMI.txt") (Join-Path $Stage "LEGGIMI.txt") -Force
Copy-Item (Join-Path $ServerMacDir "LEGGIMI.txt") (Join-Path $Stage "LEGGI-ME.txt") -Force
$aggiorna = Join-Path $ServerMacDir "LEGGIMI-AGGIORNA.txt"
if (Test-Path $aggiorna) {
    Copy-Item $aggiorna (Join-Path $Stage "LEGGIMI-AGGIORNA.txt") -Force
}

# Normalizza LF su tutti gli script bash nello stage
Get-ChildItem -Path $Stage -Recurse -Include *.sh,*.command | ForEach-Object {
    Write-LfFile $_.FullName $_.FullName
}

$fixTxt = @"
Se vedi "privilegi di accesso" su Installa-Eureka-Mac-Server.command,
apri Terminale nella cartella decompressa ed esegui:

  chmod +x Installa-Eureka-Mac-Server.command
  chmod +x scripts/*.sh
  ./Installa-Eureka-Mac-Server.command

Poi doppio clic normalmente.
"@
[System.IO.File]::WriteAllText(
    (Join-Path $Stage "SE-BLOCCA-LEGGI.txt"),
    ($fixTxt -replace "`r`n", "`n"),
    $utf8
)

$ZipName = "EurekaAI_ServerMac_$Version.zip"
$ZipPath = Join-Path $OutDir $ZipName
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

& $py -c @"
import os, zipfile
from pathlib import Path

stage = Path(r'''$Stage''')
zip_path = Path(r'''$ZipPath''')

def unix_attr(mode: int) -> int:
    return ((0o100000 | mode) << 16)

with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
    for path in sorted(stage.rglob('*')):
        if not path.is_file():
            continue
        arc = path.relative_to(stage).as_posix()
        data = path.read_bytes()
        info = zipfile.ZipInfo(arc)
        info.compress_type = zipfile.ZIP_DEFLATED
        info.create_system = 3  # Unix
        if arc.endswith('.command') or arc.endswith('.sh'):
            info.external_attr = unix_attr(0o755)
        else:
            info.external_attr = unix_attr(0o644)
        zf.writestr(info, data)
print('ZIP OK', zip_path, 'bytes', zip_path.stat().st_size)
"@

if ($LASTEXITCODE -ne 0) {
    Write-Error "Creazione ZIP con Python fallita."
}

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Pacchetto server Mac pronto:"
Write-Host "  $ZipPath"
Write-Host ""
Write-Host "Sul Mac: decomprimi -> doppio clic Installa-Eureka-Mac-Server.command"
Write-Host "Se macOS blocca: vedi SE-BLOCCA-LEGGI.txt (chmod +x)"
