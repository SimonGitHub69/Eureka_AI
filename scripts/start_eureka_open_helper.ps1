$root = "D:\Progetti\Eureka_AI"
Set-Location $root
$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw "Python virtualenv non trovato: $python" }
& $python "scripts\eureka_open_helper.py"
