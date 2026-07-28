param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class EurekaWin32 {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr hWnd);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("ole32.dll")] public static extern int CoInitializeEx(IntPtr pvReserved, uint dwCoInit);
}
"@

$resolved = (Resolve-Path -LiteralPath $Path).Path
[void][EurekaWin32]::CoInitializeEx([IntPtr]::Zero, 0x2) # COINIT_APARTMENTTHREADED

$form = New-Object System.Windows.Forms.Form
$form.Text = 'Eureka - Condividi'
$form.ShowInTaskbar = $true
$form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
$form.StartPosition = [System.Windows.Forms.FormStartPosition]::CenterScreen
$form.Size = New-Object System.Drawing.Size(280, 90)
$form.TopMost = $true
$form.MinimizeBox = $false
$form.MaximizeBox = $false
$label = New-Object System.Windows.Forms.Label
$label.Text = 'Apertura maschera Condividi...'
$label.Dock = 'Fill'
$label.TextAlign = 'MiddleCenter'
$form.Controls.Add($label)
$form.Show()
[void]$form.Activate()
[void][EurekaWin32]::ShowWindow($form.Handle, 5)
[void][EurekaWin32]::SetForegroundWindow($form.Handle)
[System.Windows.Forms.Application]::DoEvents()

try {
    $shell = New-Object -ComObject Shell.Application
    $folder = $shell.Namespace((Split-Path -LiteralPath $resolved))
    $item = $folder.ParseName((Split-Path -Leaf $resolved))
    if ($null -eq $item) {
        throw "File non trovato: $resolved"
    }

    $matched = $null
    foreach ($verb in @($item.Verbs())) {
        $name = [string]$verb.Name
        $normalized = (($name -replace '&', '') -replace '\s+', ' ').Trim().ToLowerInvariant()
        if ($normalized -eq 'condividi' -or $normalized -eq 'share') {
            $matched = $verb
            break
        }
    }
    if ($null -eq $matched) {
        throw "Verbo Condividi non trovato"
    }

    [void][EurekaWin32]::SetForegroundWindow($form.Handle)
    [System.Windows.Forms.Application]::DoEvents()

    # Preferisci InvokeVerb col nome esatto del menu (es. &Condividi)
    $verbName = [string]$matched.Name
    try {
        $item.InvokeVerb($verbName)
    } catch {
        $matched.DoIt()
    }

    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.ElapsedMilliseconds -lt 2500) {
        [System.Windows.Forms.Application]::DoEvents()
        Start-Sleep -Milliseconds 50
    }
}
finally {
    if ($form -and -not $form.IsDisposed) {
        $form.Close()
        $form.Dispose()
    }
}

exit 0
