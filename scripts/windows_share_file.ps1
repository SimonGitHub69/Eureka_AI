param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

$resolved = (Resolve-Path -LiteralPath $Path).Path
$shell = New-Object -ComObject Shell.Application
$folder = $shell.Namespace((Split-Path -LiteralPath $resolved))
$item = $folder.ParseName((Split-Path -Leaf $resolved))

if ($null -eq $item) {
    throw "File non trovato"
}

foreach ($candidate in @('share', 'Share', 'condividi', 'Condividi')) {
    try {
        $item.InvokeVerb($candidate)
        exit 0
    } catch {
        # prova il candidato successivo
    }
}

foreach ($verb in $item.Verbs()) {
    $name = [string]$verb.Name
    $normalized = ($name -replace '&', '').ToLowerInvariant()
    if ($normalized -match 'share|condividi|teilen|partager|compartir') {
        $verb.DoIt()
        exit 0
    }
}

Start-Process explorer.exe -ArgumentList @('/select,', $resolved)
throw 'Condivisione di sistema non disponibile'
