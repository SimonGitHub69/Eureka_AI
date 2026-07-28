$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$csproj = Join-Path $root 'eureka_share_net\EurekaShareNet.csproj'
$out = Join-Path $root 'share_publish'

dotnet publish $csproj -c Release -r win-x64 --self-contained false -p:PublishSingleFile=true -o $out
if ($LASTEXITCODE -ne 0) {
    throw "Publish EurekaShare fallito"
}

Copy-Item (Join-Path $out '*') $root -Force
Write-Host "OK: $(Join-Path $root 'EurekaShare.exe')"
