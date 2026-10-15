#!/bin/bash
# Eureka AI — installazione server Mac (prima installazione).
# Doppio clic dopo aver decompresso lo ZIP.
# Installa: Homebrew (se manca), PostgreSQL 16, Python, app in ~/Eureka_AI, launchd.

set -uo pipefail

clear 2>/dev/null || true
echo "========================================"
echo "  Eureka AI — Server Mac (prima install)"
echo "========================================"
echo ""

cd "$(dirname "$0")"

alert() {
  local msg="$1"
  osascript <<EOF 2>/dev/null || true
display dialog "${msg}" with title "Eureka AI Server" buttons {"OK"} default button "OK"
EOF
}

ask_text() {
  local prompt="$1"
  local def="$2"
  osascript <<EOF 2>/dev/null || true
try
  text returned of (display dialog "${prompt}" with title "Eureka AI Server" default answer "${def}" buttons {"Annulla", "OK"} default button "OK" cancel button "Annulla")
on error
  return ""
end try
EOF
}

confirm() {
  local msg="$1"
  osascript <<EOF 2>/dev/null || true
try
  button returned of (display dialog "${msg}" with title "Eureka AI Server" buttons {"Annulla", "Installa"} default button "Installa" cancel button "Annulla")
on error
  return ""
end try
EOF
}

# Individua root pacchetto (manage.py)
find_package_root() {
  local here cand
  here="$(cd "$(dirname "$0")" && pwd)"
  for cand in \
    "$here" \
    "$(dirname "$here")" \
    "$(dirname "$(dirname "$here")")"
  do
    if [ -f "${cand}/manage.py" ]; then
      echo "$cand"
      return 0
    fi
  done
  return 1
}

SOURCE_ROOT="$(find_package_root)" || {
  alert "Impossibile trovare manage.py nel pacchetto.
Decomprimi lo ZIP completo e riesegui Installa-Eureka-Mac-Server.command"
  echo "ERRORE: root pacchetto non trovata."
  read -r -p "Premi Invio per chiudere..." _
  exit 1
}

INSTALL_ROOT="${HOME}/Eureka_AI"

# Evita "aggiornamento" a vuoto: se lanci l'installer DENTRO ~/Eureka_AI,
# sorgente = destinazione e i file non cambiano mai (resta 1.0.15).
SRC_RESOLVED="$(cd "$SOURCE_ROOT" && pwd -P)"
DST_RESOLVED="$(mkdir -p "$INSTALL_ROOT"; cd "$INSTALL_ROOT" && pwd -P)"
if [ "$SRC_RESOLVED" = "$DST_RESOLVED" ]; then
  alert "Hai avviato l'installer dalla cartella gia installata:

${INSTALL_ROOT}

Cosi non si aggiorna nulla.

Cosa fare:
1) Decomprimi EurekaAI_ServerMac_*.zip in Download o Scrivania
2) Doppio clic su Installa-Eureka-Mac-Server.command DENTRO quella cartella decompressa
   (non da ~/Eureka_AI)"
  echo "ERRORE: SOURCE_ROOT == INSTALL_ROOT ($SRC_RESOLVED)"
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

read_pkg_version() {
  local root="$1"
  local pyf="${root}/package.json"
  local ver=""
  if [ ! -f "$pyf" ]; then
    echo ""
    return 0
  fi
  ver="$(/usr/bin/python3 -c "import json; print(json.load(open('''${pyf}''', encoding='utf-8')).get('version','').strip())" 2>/dev/null || true)"
  if [ -z "$ver" ]; then
    ver="$(/usr/bin/sed -n '1,12p' "$pyf" | /usr/bin/grep -E '"version"' | /usr/bin/head -1 | /usr/bin/sed -E 's/.*"version"[[:space:]]*:[[:space:]]*"([^"]+)".*/\1/')"
  fi
  echo "$ver"
}

SRC_VER="$(read_pkg_version "$SOURCE_ROOT")"
OLD_VER="$(read_pkg_version "$INSTALL_ROOT")"
[ -z "$SRC_VER" ] && SRC_VER="(sconosciuta)"
[ -z "$OLD_VER" ] && OLD_VER="(non installato)"

DEFAULT_PORT="8000"

PORT="$(ask_text "Porta HTTP del server Eureka (default 8000):" "$DEFAULT_PORT")"
if [ -z "$PORT" ]; then
  echo "Installazione annullata."
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi
PORT="$(echo "$PORT" | tr -cd '0-9')"
if [ -z "$PORT" ]; then PORT=8000; fi

BTN="$(confirm "Aggiorna / Installa Eureka AI Server?

Versione pacchetto:  ${SRC_VER}
Versione attuale:    ${OLD_VER}
Destinazione:        ${INSTALL_ROOT}
Sorgente:            ${SOURCE_ROOT}
Porta:               ${PORT}

Il .env esistente viene preservato (poi allineata EUREKA_VERSION).
Puo richiedere password Mac e alcuni minuti.")"
if [ "$BTN" != "Installa" ]; then
  echo "Installazione annullata."
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

LOG_FILE="${TMPDIR:-/tmp}/eureka_mac_install_$$.log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "Log: $LOG_FILE"
echo "Sorgente: $SOURCE_ROOT"
echo "Destinazione: $INSTALL_ROOT"
echo "Porta: $PORT"
echo ""

# Homebrew nel PATH (Apple Silicon / Intel) — anche dopo install fresca
load_brew() {
  export PATH="/opt/homebrew/bin:/usr/local/bin:${PATH}"
  if [ -x /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
  elif [ -x /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
  fi
}
load_brew

# 1) Ferma servizio prima della copia (altrimenti file bloccati / copia incompleta)
echo "=== Stop servizio (se presente) ==="
if [ -x "${INSTALL_ROOT}/scripts/install_service_launchd.sh" ]; then
  bash "${INSTALL_ROOT}/scripts/install_service_launchd.sh" --unload || true
fi
pkill -f "waitress.*config.wsgi" 2>/dev/null || true
sleep 1

# 2) Copia progetto (non sovrascrivere .env)
echo "=== Copia file ==="
mkdir -p "$INSTALL_ROOT"
ENV_BACKUP=""
if [ -f "${INSTALL_ROOT}/.env" ]; then
  ENV_BACKUP="$(mktemp)"
  cp "${INSTALL_ROOT}/.env" "$ENV_BACKUP"
fi

echo "package.json sorgente:"
head -5 "${SOURCE_ROOT}/package.json" || true

RSYNC_OK=0
if command -v rsync >/dev/null 2>&1; then
  if rsync -a --checksum \
    --exclude '.git' \
    --exclude '.venv' \
    --exclude 'node_modules' \
    --exclude '__pycache__' \
    --exclude '.cursor' \
    --exclude 'staticfiles' \
    --exclude 'logs' \
    --exclude 'htmlcov' \
    --exclude '.pytest_cache' \
    --exclude 'installazione/dist' \
    --exclude '.env' \
    --exclude 'media' \
    "${SOURCE_ROOT}/" "${INSTALL_ROOT}/"
  then
    RSYNC_OK=1
  else
    echo "WARN: rsync exit $? — riprovo con ditto"
  fi
fi

if [ "$RSYNC_OK" != "1" ]; then
  /usr/bin/ditto --norsrc "$SOURCE_ROOT" "$INSTALL_ROOT" || {
    alert "Copia file fallita (rsync/ditto).
Log: ${LOG_FILE}"
    read -r -p "Premi Invio per chiudere..." _
    exit 1
  }
fi

# Forza i file critici (evita skip rsync / permessi)
for f in package.json manage.py config/settings.py; do
  if [ -f "${SOURCE_ROOT}/${f}" ]; then
    mkdir -p "$(dirname "${INSTALL_ROOT}/${f}")"
    /bin/cp -f "${SOURCE_ROOT}/${f}" "${INSTALL_ROOT}/${f}" || {
      alert "Impossibile copiare ${f} in ${INSTALL_ROOT}.
Controlla permessi (cartella di sola lettura?)."
      exit 1
    }
  fi
done
# Copia ricorsiva apps/ e scripts/ essenziali
/bin/cp -Rf "${SOURCE_ROOT}/apps" "${INSTALL_ROOT}/" 2>/dev/null || true
/bin/cp -Rf "${SOURCE_ROOT}/scripts" "${INSTALL_ROOT}/" 2>/dev/null || true
/bin/cp -Rf "${SOURCE_ROOT}/static/eureka" "${INSTALL_ROOT}/static/" 2>/dev/null || true
/bin/cp -Rf "${SOURCE_ROOT}/templates" "${INSTALL_ROOT}/" 2>/dev/null || true
/bin/cp -Rf "${SOURCE_ROOT}/installazione/server-mac" "${INSTALL_ROOT}/installazione/" 2>/dev/null || true

if [ -n "$ENV_BACKUP" ] && [ -f "$ENV_BACKUP" ]; then
  cp "$ENV_BACKUP" "${INSTALL_ROOT}/.env"
  rm -f "$ENV_BACKUP"
fi

echo "package.json destinazione dopo copia:"
head -5 "${INSTALL_ROOT}/package.json" || true

# Verifica che la copia abbia portato la nuova versione
NEW_VER="$(read_pkg_version "$INSTALL_ROOT")"
echo "Versione dopo copia: ${NEW_VER} (attesa ${SRC_VER})"
if [ -n "$SRC_VER" ] && [ "$SRC_VER" != "(sconosciuta)" ] && [ "$NEW_VER" != "$SRC_VER" ]; then
  alert "Aggiornamento incompleto: package.json e ancora ${NEW_VER}, atteso ${SRC_VER}.

Sorgente: ${SOURCE_ROOT}
Destinazione: ${INSTALL_ROOT}

Prova in Terminale:
  cp -f \"${SOURCE_ROOT}/package.json\" ~/Eureka_AI/package.json
  grep version ~/Eureka_AI/package.json
  ~/Eureka_AI/scripts/install_service_launchd.sh

Log: ${LOG_FILE}"
  echo "ERRORE: versione dopo copia=${NEW_VER} != sorgente=${SRC_VER}"
  echo "--- sorgente ---"; cat "${SOURCE_ROOT}/package.json" | head -8
  echo "--- destinazione ---"; cat "${INSTALL_ROOT}/package.json" | head -8
  ls -la "${SOURCE_ROOT}/package.json" "${INSTALL_ROOT}/package.json" || true
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

# Allinea subito EUREKA_VERSION nel .env (anche se prod_install fallisse dopo)
if [ -n "$NEW_VER" ] && [ "$NEW_VER" != "(sconosciuta)" ] && [ -f "${INSTALL_ROOT}/.env" ]; then
  TMP="$(mktemp)"
  if grep -q '^EUREKA_VERSION=' "${INSTALL_ROOT}/.env"; then
    awk -v v="$NEW_VER" 'BEGIN{FS=OFS="="} $1=="EUREKA_VERSION"{$0="EUREKA_VERSION="v} {print}' "${INSTALL_ROOT}/.env" > "$TMP"
  else
    cat "${INSTALL_ROOT}/.env" > "$TMP"
    printf '\nEUREKA_VERSION=%s\n' "$NEW_VER" >> "$TMP"
  fi
  mv "$TMP" "${INSTALL_ROOT}/.env"
  echo "EUREKA_VERSION=${NEW_VER}"
fi

chmod +x "${INSTALL_ROOT}/scripts/"*.sh 2>/dev/null || true
chmod +x "${INSTALL_ROOT}/installazione/server-mac/"*.command 2>/dev/null || true

# 2) PostgreSQL
echo ""
echo "=== PostgreSQL ==="
URL_FILE="$(mktemp)"
export EUREKA_DB_URL_FILE="$URL_FILE"
if ! bash "${INSTALL_ROOT}/scripts/install_postgresql_mac.sh"; then
  alert "Installazione PostgreSQL fallita.
Vedi il log: ${LOG_FILE}"
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi
DATABASE_URL="$(tail -n 1 "$URL_FILE" | tr -d '\r')"
rm -f "$URL_FILE" "${URL_FILE}.password" 2>/dev/null || true
if [ -z "$DATABASE_URL" ] || [[ "$DATABASE_URL" != postgres://* ]]; then
  alert "DATABASE_URL non generato correttamente.
Vedi: ${LOG_FILE}"
  exit 1
fi
echo "DATABASE_URL configurato."

# PATH brew aggiornato (install_postgresql lo ha creato in un subshell)
load_brew

# Scrivi/aggiorna .env con DATABASE_URL (senza cancellare un .env gia configurato:
# aggiorna solo DATABASE_URL se assente o ancora di esempio)
ENV_FILE="${INSTALL_ROOT}/.env"
if [ ! -f "$ENV_FILE" ] && [ -f "${INSTALL_ROOT}/.env.example" ]; then
  cp "${INSTALL_ROOT}/.env.example" "$ENV_FILE"
fi
if [ -f "$ENV_FILE" ]; then
  if grep -q '^DATABASE_URL=' "$ENV_FILE"; then
    CUR_DB="$(grep '^DATABASE_URL=' "$ENV_FILE" | head -1 | cut -d= -f2-)"
    if [ -z "$CUR_DB" ] || echo "$CUR_DB" | grep -q 'eureka:eureka@'; then
      TMP="$(mktemp)"
      awk -v v="$DATABASE_URL" 'BEGIN{FS=OFS="="} $1=="DATABASE_URL"{$0="DATABASE_URL="v} {print}' "$ENV_FILE" > "$TMP"
      mv "$TMP" "$ENV_FILE"
    fi
  else
    printf '\nDATABASE_URL=%s\n' "$DATABASE_URL" >> "$ENV_FILE"
  fi
else
  printf 'DEBUG=False\nSECRET_KEY=change-me-in-production\nALLOWED_HOSTS=127.0.0.1,localhost\nCSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000\nDATABASE_URL=%s\n' "$DATABASE_URL" > "$ENV_FILE"
fi

# 3) prod_install
echo ""
echo "=== Ambiente Python / Django ==="
export DATABASE_URL
export INSTALL_PYTHON_IF_MISSING=1
export PORT
if ! bash "${INSTALL_ROOT}/scripts/prod_install.sh"; then
  alert "prod_install fallito.
Vedi: ${LOG_FILE}"
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

# 4) launchd
echo ""
echo "=== Servizio launchd ==="
export LISTEN_HOST=0.0.0.0
export PORT
export THREADS=6
if ! bash "${INSTALL_ROOT}/scripts/install_service_launchd.sh"; then
  alert "Registrazione servizio fallita.
Puoi avviare manualmente:
  cd ${INSTALL_ROOT}
  ./scripts/prod_start.sh
Log: ${LOG_FILE}"
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi

# Attendi risposta HTTP
echo "Attesa avvio server..."
OK=0
for _ in $(seq 1 20); do
  CODE="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PORT}/" 2>/dev/null || echo 000)"
  if [ "$CODE" = "200" ] || [ "$CODE" = "302" ] || [ "$CODE" = "301" ]; then
    OK=1
    break
  fi
  sleep 1
done

URL="http://127.0.0.1:${PORT}/"
HOST_SHORT="$(scutil --get LocalHostName 2>/dev/null || hostname -s 2>/dev/null || echo "")"
LAN_URL=""
if [ -n "$HOST_SHORT" ]; then
  LAN_URL="http://${HOST_SHORT}.local:${PORT}/"
fi
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
IP_URL=""
if [ -n "$LAN_IP" ]; then
  IP_URL="http://${LAN_IP}:${PORT}/"
fi
echo ""
echo "========================================"
echo " Eureka AI installato"
echo " Path:  $INSTALL_ROOT"
echo " Locale: $URL"
[ -n "$LAN_URL" ] && echo " LAN:    $LAN_URL  (consigliato per i client — stabile con DHCP)"
[ -n "$IP_URL" ] && echo " IP:     $IP_URL  (puo cambiare con Wi-Fi DHCP)"
echo " HTTP:  ${CODE:-?} (ok=${OK})"
echo " Log:   $LOG_FILE"
echo "========================================"

CLIENT_HINT="${LAN_URL:-$IP_URL}"
[ -z "$CLIENT_HINT" ] && CLIENT_HINT="$URL"
alert "Eureka AI Server e stato installato / aggiornato.

Versione: ${NEW_VER:-$SRC_VER}
Cartella: ${INSTALL_ROOT}
Locale: ${URL}
Client (consigliato): ${CLIENT_HINT}

Usa .local sui client: non dipende dal DHCP.
Il servizio riparte al login utente Mac.
Per fermarlo:
  cd ${INSTALL_ROOT}
  ./scripts/install_service_launchd.sh --unload"

open "$URL" 2>/dev/null || true

echo ""
read -r -p "Premi Invio per chiudere..." _
