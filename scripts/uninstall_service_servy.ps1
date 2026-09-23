# Disinstalla il servizio Windows Eureka AI gestito da Servy.
# Eseguire come Amministratore:
#   .\scripts\uninstall_service_servy.ps1

param(
    [string]$ServiceName = "EurekaAI",
    [switch]$RemoveFirewall,
    [int]$Port = 8000
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

Assert-Admin

$ServyCli = Resolve-ServyCli
if (-not $ServyCli) {
    Write-Error "servy-cli non trovato. Il servizio potrebbe comunque esistere: usa sc.exe delete $ServiceName"
}

Write-Host "Stop servizio $ServiceName..."
& $ServyCli stop --quiet --name=$ServiceName 2>$null
Start-Sleep -Seconds 1

Write-Host "Uninstall Servy..."
& $ServyCli uninstall --quiet --name=$ServiceName
if ($LASTEXITCODE -ne 0) {
    Write-Warning "uninstall exit $LASTEXITCODE - provo sc.exe delete"
    & sc.exe stop $ServiceName
    & sc.exe delete $ServiceName
}

if ($RemoveFirewall) {
    $ruleName = "Eureka AI HTTP $Port"
    Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue |
        Remove-NetFirewallRule -ErrorAction SilentlyContinue
    Write-Host "Regola firewall rimossa (se presente): $ruleName"
}

Write-Host "Fatto."
