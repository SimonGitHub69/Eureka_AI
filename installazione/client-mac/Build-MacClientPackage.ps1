# Costruisce lo ZIP client Mac da consegnare al cliente.
# Imposta i bit Unix eseguibili (chmod +x) su Installa-Eureka-Mac.command
# cosi' il doppio clic da Finder funziona anche se lo ZIP e generato su Windows.
#
# Uso (dalla root progetto):
#   .\installazione\client-mac\Build-MacClientPackage.ps1

param(
    [string]$Version = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$ClientMacDir = $PSScriptRoot
$InstallazioneDir = Split-Path -Parent $ClientMacDir
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

$Stage = Join-Path $env:TEMP ("EurekaAI_ClientMac_stage_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Write-Host "Staging client Mac -> $Stage"

Copy-Item (Join-Path $ClientMacDir "LEGGIMI.txt") (Join-Path $Stage "LEGGIMI.txt") -Force
Copy-Item (Join-Path $ClientMacDir "LEGGIMI.txt") (Join-Path $Stage "LEGGI-ME.txt") -Force

$cmdSrc = Join-Path $ClientMacDir "Installa-Eureka-Mac.command"
$cmdDst = Join-Path $Stage "Installa-Eureka-Mac.command"
# LF obbligatori per script Mac + versione da package.json
$raw = [System.IO.File]::ReadAllText($cmdSrc)
$raw = $raw -replace "`r`n", "`n" -replace "`r", "`n"
$raw = $raw.Replace("__EUREKA_VERSION__", $Version)
$utf8 = New-Object System.Text.UTF8Encoding $false
[System.IO.File]::WriteAllText($cmdDst, $raw, $utf8)

# Fallback se unzip perde i bit: script da eseguire in Terminale
$fixTxt = @"
Se vedi "privilegi di accesso" su Installa-Eureka-Mac.command,
apri Terminale, vai nella cartella decompressa ed esegui:

  chmod +x Installa-Eureka-Mac.command
  ./Installa-Eureka-Mac.command

Poi doppio clic normalmente.
"@
[System.IO.File]::WriteAllText((Join-Path $Stage "SE-BLOCCA-LEGGI.txt"), ($fixTxt -replace "`r`n", "`n"), $utf8)

$icon = Join-Path $Root "static\eureka\icons\icon-512.png"
if (Test-Path $icon) {
    Copy-Item $icon (Join-Path $Stage "eureka-icon.png") -Force
}

$ZipName = "EurekaAI_ClientMac_$Version.zip"
$ZipPath = Join-Path $OutDir $ZipName
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

# Python: ZIP con external_attr Unix eseguibile (0o100755)
$py = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $py)) { $py = "python" }

$stageFwd = $Stage.Replace("\", "/")
$zipFwd = $ZipPath.Replace("\", "/")

& $py -c @"
import os, zipfile
from pathlib import Path

stage = Path(r'''$Stage''')
zip_path = Path(r'''$ZipPath''')

def unix_attr(mode: int) -> int:
    # file type regular (0o100000) + permission bits
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
        if arc.endswith('.command') or arc.endswith('/EurekaAI') or arc == 'EurekaAI':
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
Write-Host "Pacchetto client Mac pronto:"
Write-Host "  $ZipPath"
Write-Host ""
Write-Host "Sul Mac: decomprimi -> doppio clic Installa-Eureka-Mac.command"
Write-Host "Se macOS blocca: vedi SE-BLOCCA-LEGGI.txt (chmod +x)"
