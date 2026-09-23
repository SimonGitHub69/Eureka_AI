@echo off
REM Aggiorna Eureka AI gia installato (Admin) - non sovrascrive .env
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% NEQ 0 (
  echo Richiesta privilegi Amministratore...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0Aggiorna-EurekaAI-Server.ps1\"' -Wait"
  exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Aggiorna-EurekaAI-Server.ps1"
exit /b %ERRORLEVEL%
