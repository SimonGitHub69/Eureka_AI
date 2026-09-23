@echo off
REM Auto-elevazione e avvio installazione Eureka AI (Windows Server + Servy)
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if %errorLevel% NEQ 0 (
  echo Richiesta privilegi Amministratore...
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process -FilePath 'powershell.exe' -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File \"%~dp0Installa-EurekaAI-Server.ps1\" -InstallServy -InstallPython' -Wait"
  exit /b %ERRORLEVEL%
)

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Installa-EurekaAI-Server.ps1" -InstallServy -InstallPython
exit /b %ERRORLEVEL%
