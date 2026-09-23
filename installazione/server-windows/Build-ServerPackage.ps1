# Costruisce il pacchetto autoinstallante Eureka AI per Windows Server.
# Output: installazione\dist\EurekaAI_ServerWindows_<ver>.zip (+ .exe SFX se 7z disponibile)
#
# Uso (dalla root progetto):
#   .\installazione\server-windows\Build-ServerPackage.ps1
#   .\installazione\server-windows\Build-ServerPackage.ps1 -Version 1.0.1

param(
    [string]$Version = "",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"

$ServerWinDir = $PSScriptRoot
$InstallazioneDir = Split-Path -Parent $ServerWinDir
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

$Stage = Join-Path $env:TEMP ("EurekaAI_ServerWindows_stage_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $Stage | Out-Null

Write-Host "Staging da $Root -> $Stage"

$excludeDirNames = @(
    ".git", ".venv", "node_modules", "__pycache__", ".cursor",
    "staticfiles", "logs", "htmlcov", ".pytest_cache", "dist",
    "agent-transcripts", "agent-tools"
)

# Copia selettiva
Get-ChildItem -Path $Root -Force | ForEach-Object {
    $name = $_.Name
    if ($excludeDirNames -contains $name) { return }
    if ($name -eq "installazione") {
        # includi solo server-windows (non dist)
        $destInst = Join-Path $Stage "installazione\server-windows"
        New-Item -ItemType Directory -Force -Path $destInst | Out-Null
        Copy-Item -Path (Join-Path $ServerWinDir "*") -Destination $destInst -Recurse -Force
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

# Entry points in root dello stage (comodi dopo unzip)
Copy-Item (Join-Path $ServerWinDir "Installa.cmd") (Join-Path $Stage "Installa.cmd") -Force
Copy-Item (Join-Path $ServerWinDir "Installa-EurekaAI-Server.ps1") (Join-Path $Stage "Installa-EurekaAI-Server.ps1") -Force
if (Test-Path (Join-Path $ServerWinDir "Aggiorna.cmd")) {
    Copy-Item (Join-Path $ServerWinDir "Aggiorna.cmd") (Join-Path $Stage "Aggiorna.cmd") -Force
}
if (Test-Path (Join-Path $ServerWinDir "Aggiorna-EurekaAI-Server.ps1")) {
    Copy-Item (Join-Path $ServerWinDir "Aggiorna-EurekaAI-Server.ps1") (Join-Path $Stage "Aggiorna-EurekaAI-Server.ps1") -Force
}
Copy-Item (Join-Path $ServerWinDir "LEGGIMI-SERVY.md") (Join-Path $Stage "LEGGIMI-SERVER-WINDOWS.md") -Force

# Patch Installa.cmd path: dallo stage root punta a Installa-EurekaAI-Server.ps1 locale
# (già ok). Get-PackageRoot gestisce manage.py nella stessa cartella.

$ZipName = "EurekaAI_ServerWindows_$Version.zip"
$ZipPath = Join-Path $OutDir $ZipName
if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

Write-Host "Creo ZIP: $ZipPath"
Compress-Archive -Path (Join-Path $Stage "*") -DestinationPath $ZipPath -CompressionLevel Optimal

$ExePath = $null
$sevenZip = @(
    "${env:ProgramFiles}\7-Zip\7z.exe",
    "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($sevenZip) {
    $ExeName = "EurekaAI_ServerWindows_$Version.exe"
    $ExePath = Join-Path $OutDir $ExeName
    if (Test-Path $ExePath) { Remove-Item $ExePath -Force }
    $cfg = Join-Path $Stage "sfx_config.txt"
    @"
;!@Install@!UTF-8!
Title="Eureka AI Server Windows $Version"
BeginPrompt="Installare Eureka AI su questo Windows Server?\nVerranno richiesti privilegi Amministratore.\nServy verra' usato per il servizio Windows."
RunProgram="Installa.cmd"
;!@InstallEnd@!
"@ | Set-Content -Path $cfg -Encoding UTF8
    $sfx = Join-Path (Split-Path $sevenZip) "7z.sfx"
    if (-not (Test-Path $sfx)) {
        Write-Warning "7z.sfx non trovato: salto EXE autoestraente (resta lo ZIP)."
    } else {
        $inner = Join-Path $env:TEMP "eureka_sfx_inner.7z"
        if (Test-Path $inner) { Remove-Item $inner -Force }
        & $sevenZip a -t7z -mx=7 $inner (Join-Path $Stage "*") | Out-Null
        cmd /c "copy /b `"$sfx`" + `"$cfg`" + `"$inner`" `"$ExePath`"" | Out-Null
        Remove-Item $inner -Force -ErrorAction SilentlyContinue
        if (Test-Path $ExePath) {
            Write-Host "EXE autoinstallante: $ExePath"
        }
    }
} else {
    Write-Host "7-Zip non trovato: generato solo ZIP. (Opzionale: installa 7-Zip per .exe SFX)"
}

Remove-Item $Stage -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Pacchetto pronto:"
Write-Host "  ZIP: $ZipPath"
if ($ExePath -and (Test-Path $ExePath)) {
    Write-Host "  EXE: $ExePath"
}
Write-Host ""
Write-Host "Sul server: decomprimi (o esegui EXE) -> Installa.cmd (Admin) -> configura .env"
