# Eureka AI — Installazione Windows Server con Servy

Questo pacchetto installa **Eureka AI** (Django + Waitress) come **servizio Windows** usando **[Servy](https://github.com/aelassas/servy)** (`servy-cli`).

Documentazione ufficiale Servy:

- [Installation Guide](https://github.com/aelassas/servy/wiki/Installation-Guide)
- [Servy CLI](https://github.com/aelassas/servy/wiki/Servy-CLI)
- [Automation & CI/CD](https://github.com/aelassas/servy/wiki/Automation-&-CI-CD)
- [Examples & Recipes](https://github.com/aelassas/servy/wiki/Examples-&-Recipes) (Python)
- [Security](https://github.com/aelassas/servy/wiki/Security)

---

## Requisiti server

| Componente | Note |
|---|---|
| Windows Server 2016+ (o Windows 10/11) | x64 |
| Privilegi Amministratore | Obbligatori per servizio e firewall |
| Python 3.11+ | Installato automaticamente via winget se usi `Installa.cmd` (`-InstallPython`) |
| PostgreSQL | **Obbligatorio.** Locale sul server oppure remoto (`DATABASE_URL`). Vedi sezione sotto. |
| (Opzionale) Node.js / npm | Solo se serve ricostruire `static/vendor` |
| winget | Per installare Python e Servy in automatico (se presente) |

### PostgreSQL (se non e ancora installato)

Eureka AI usa PostgreSQL. Senza DB, `migrate` fallisce.

**Opzione A - installer ufficiale (consigliata su Server senza winget)**

1. Scarica: https://www.postgresql.org/download/windows/
2. Installa (porta **5432**, annota la password di `postgres`).
3. Come Amministratore, dalla cartella Eureka:
   ```powershell
   cd C:\Eureka_AI
   .\scripts\install_postgresql_windows.ps1 -SkipInstall -DbPassword "ScegliUnaPassword"
   ```
4. In `C:\Eureka_AI\.env`:
   ```env
   DATABASE_URL=postgres://eureka:ScegliUnaPassword@127.0.0.1:5432/eureka_ai
   ```
5. Riprendi:
   ```powershell
   .\scripts\prod_install.ps1
   .\scripts\install_service_servy.ps1 -InstallServyIfMissing
   ```

**Opzione B - script completo** (prova winget, altrimenti stampa le istruzioni):

```powershell
cd C:\Eureka_AI
.\scripts\install_postgresql_windows.ps1 -DbPassword "ScegliUnaPassword"
```

---

## Installazione rapida (pacchetto autoinstallante)

1. Copia sul server lo **ZIP** `EurekaAI_ServerWindows_<ver>.zip` (o l'**EXE** SFX se generato).
2. Decomprimi (o esegui l'EXE).
3. Installa **PostgreSQL** (vedi sopra) se non e presente.
4. Esegui **`Installa.cmd`** (chiede UAC).
5. Configura **`C:\Eureka_AI\.env`**:
   - `DEBUG=False`
   - `SECRET_KEY=` valore sicuro
   - `ALLOWED_HOSTS=` hostname/IP del server
   - `DATABASE_URL=` connessione PostgreSQL
6. Se hai modificato `.env` dopo il primo avvio:
   ```powershell
   servy-cli restart --name=EurekaAI
   ```
7. Apri `http://<server>:8000/`

Parametri utili dell'installer:

```powershell
.\Installa-EurekaAI-Server.ps1 -InstallServy -InstallPython -InstallRoot "C:\Eureka_AI" -Port 8000
```

Se Python e gia presente nel PATH, `-InstallPython` non lo reinstalla.
---

## Cosa fa l’installer

1. Copia i file in `-InstallRoot` (default `C:\Eureka_AI`) senza sovrascrivere un `.env` già presente.
2. Esegue `scripts\prod_install.ps1` → venv, `pip install -r requirements.txt`, `migrate`, `collectstatic`.
3. Installa **Servy** via `winget` se usi `-InstallServy` / `Installa.cmd`.
4. Registra il servizio con **servy-cli install** (idempotente: install = create/update).
5. Apre la porta TCP sul firewall Windows.
6. Avvia il servizio.

---

## Servy — istruzioni complete

### 1. Installare Servy

**WinGet (consigliato, silenzioso):**

```powershell
# PowerShell Amministratore
winget install --id aelassas.Servy -e --accept-package-agreements --accept-source-agreements --silent
```

**Chocolatey:**

```powershell
choco install -y servy
```

**Manuale:** scaricare l’installer da  
https://github.com/aelassas/servy/releases  

Silent install Inno Setup (esempio):

```powershell
.\servy-<version>-x64-installer.exe /VERYSILENT /NORESTART /SUPPRESSMSGBOXES /SP- /CLOSEAPPLICATIONS /NOCANCEL
```

Solo CLI:

```text
/SetupType=custom /Components=install_cli
```

Dopo l’installazione l’eseguibile tipico è:

```text
C:\Program Files\Servy\servy-cli.exe
```

(è anche nel `PATH` di sistema).

Verifica:

```powershell
servy-cli --version
# oppure
& "$env:ProgramFiles\Servy\servy-cli.exe" version
```

### 2. Registrare Eureka AI come servizio

Dalla cartella di installazione (es. `C:\Eureka_AI`), **come Amministratore**:

```powershell
.\scripts\install_service_servy.ps1 -InstallServyIfMissing
```

Equivalente manuale Servy CLI (stesso risultato):

```powershell
$Root = "C:\Eureka_AI"
$Python = Join-Path $Root ".venv\Scripts\python.exe"
$Logs = Join-Path $Root "logs"
New-Item -ItemType Directory -Force -Path $Logs | Out-Null

# Pattern sicuro consigliato da Servy: parametri/env in variabili d'ambiente di processo
$env:SERVY_PROCESS_PARAMETERS = "-m waitress --listen=0.0.0.0:8000 --threads=6 config.wsgi:application"
$env:SERVY_ENVIRONMENT_VARIABLES = "DJANGO_SETTINGS_MODULE=config.settings"

servy-cli install `
  --quiet `
  --name="EurekaAI" `
  --displayName="Eureka AI" `
  --description="Eureka AI (Django + Waitress)" `
  --path="$Python" `
  --startupDir="$Root" `
  --startupType="Automatic" `
  --stdout="$Logs\waitress.out.log" `
  --stderr="$Logs\waitress.err.log" `
  --enableSizeRotation `
  --rotationSize=10 `
  --maxRotations=12 `
  --recoveryAction="RestartService" `
  --maxRestartAttempts=5 `
  --startTimeout=60 `
  --stopTimeout=30

Remove-Item Env:SERVY_PROCESS_PARAMETERS, Env:SERVY_ENVIRONMENT_VARIABLES -ErrorAction SilentlyContinue

servy-cli start --quiet --name="EurekaAI"
servy-cli status --name="EurekaAI"
```

> **Sicurezza Servy:** non passare secret in `--params` / `--envVars` sulla riga di comando in produzione. Usare `SERVY_PROCESS_PARAMETERS` e `SERVY_ENVIRONMENT_VARIABLES` come sopra ([Security](https://github.com/aelassas/servy/wiki/Security)).

### 3. Comandi di gestione Servy

| Azione | Comando |
|---|---|
| Stato | `servy-cli status --name=EurekaAI` |
| Avvio | `servy-cli start --name=EurekaAI` |
| Stop | `servy-cli stop --name=EurekaAI` |
| Restart | `servy-cli restart --name=EurekaAI` |
| Aggiorna config | rieseguire `install` (idempotente) |
| Disinstalla | `servy-cli uninstall --name=EurekaAI` |
| Export config | `servy-cli export --name=EurekaAI --configPath=C:\temp\eureka.json` |
| Import config | `servy-cli import --configPath=C:\temp\eureka.json --install` |

Anche da Windows:

```powershell
Get-Service EurekaAI
Restart-Service EurekaAI
# oppure
sc.exe start EurekaAI
```

GUI: **Servy Manager** / **Servy Desktop App** per monitorare CPU/RAM e log.

### 4. Account di servizio (opzionale)

Default: **Local System**.

Per account dedicato:

```powershell
$env:SERVY_PASSWORD = "********"
servy-cli install --name="EurekaAI" --path="..." --user="DOMINIO\svc-eureka" ...
Remove-Item Env:SERVY_PASSWORD
```

Poi applicare lo script di hardening Servy  
`Set-ServyExePermissions.ps1` come da [Security wiki](https://github.com/aelassas/servy/wiki/Security#executable-permission-hardening-mandatory)  
e concedere **Modify** su `%ProgramData%\Servy` e sulla cartella `C:\Eureka_AI` (logs, `.env` protetto).

### 5. Dipendenze servizio (es. PostgreSQL)

Se PostgreSQL è un servizio Windows locale:

```powershell
servy-cli install ... --deps="postgresql-x64-16"
```

(sostituire col nome reale del servizio da `Get-Service *postgres*`).

### 6. Log

- Applicazione: `C:\Eureka_AI\logs\waitress.out.log` / `waitress.err.log`
- Servy: log interni Servy (Manager) + Event Viewer se configurato

Rotazione: `--enableSizeRotation --rotationSize=10 --maxRotations=12`

### 7. Disinstallazione servizio

```powershell
.\scripts\uninstall_service_servy.ps1 -RemoveFirewall
```

---

## Script di progetto (senza pacchetto)

Dalla root del repository:

```powershell
.\scripts\prod_install.ps1
.\scripts\prod_start.ps1                    # console (test)
.\scripts\install_service_servy.ps1 -InstallServyIfMissing
.\scripts\uninstall_service_servy.ps1
```

---

## Build del pacchetto (macchina di sviluppo)

```powershell
cd D:\Progetti\Eureka_AI
.\installazione\server-windows\Build-ServerPackage.ps1
```

Output in `installazione\dist\`:

- `EurekaAI_ServerWindows_<ver>.zip` — sempre
- `EurekaAI_ServerWindows_<ver>.exe` — se è installato **7-Zip** con `7z.sfx`

---

## Checklist post-install

- [ ] `.env` con `DEBUG=False`
- [ ] `SECRET_KEY` unico
- [ ] `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` corretti
- [ ] PostgreSQL raggiungibile; migrate ok
- [ ] `servy-cli status --name=EurekaAI` → **Running**
- [ ] Firewall TCP 8000 (o porta scelta)
- [ ] Backup di `.env` e database

---

## Risoluzione problemi

| Problema | Cosa controllare |
|---|---|
| Servizio non parte | `logs\waitress.err.log`, `.env`, DB, `servy-cli status` |
| `servy-cli` non trovato | Reinstallare Servy; aprire nuova shell Admin |
| Porta occupata | Cambiare `-Port` e rieseguire `install_service_servy.ps1` |
| Static 404 | `.\scripts\prod_install.ps1` (collectstatic) + riavvio servizio |
| Python mancante | Installare Python 3.11+ x64 con PATH |
| winget assente | Installer manuale Servy da GitHub Releases |
