#!/bin/bash
# Installa Eureka AI in /Applicazioni (richiede password Mac se serve).
# Doppio clic dopo aver decompresso lo ZIP.

set -uo pipefail

clear 2>/dev/null || true
echo "========================================"
echo "  Eureka AI — installazione client Mac"
echo "========================================"
echo ""

cd "$(dirname "$0")"

# Preferisci nome-mac.local (stabile con DHCP); IP solo se .local non risolve.
DEFAULT_URL="http://eureka-server.local:8000"
DEFAULT_PC="MAC-$(scutil --get LocalHostName 2>/dev/null | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9' | cut -c1-8)"
if [ -z "${DEFAULT_PC}" ] || [ "${DEFAULT_PC}" = "MAC-" ]; then
  DEFAULT_PC="MAC-$(printf '%04d' $((RANDOM % 10000)))"
fi

ask_text() {
  local prompt="$1"
  local def="$2"
  osascript <<EOF 2>/dev/null || true
try
  text returned of (display dialog "${prompt}" with title "Eureka AI" default answer "${def}" buttons {"Annulla", "OK"} default button "OK" cancel button "Annulla")
on error
  return ""
end try
EOF
}

alert() {
  local msg="$1"
  osascript <<EOF 2>/dev/null || true
display dialog "${msg}" with title "Eureka AI" buttons {"OK"} default button "OK"
EOF
}

SERVER_URL=$(ask_text "Indirizzo server (meglio http://NomeMac.local:8000, stabile con DHCP; oppure http://192.168.x.x:8000):" "$DEFAULT_URL")
if [ -z "$SERVER_URL" ]; then
  echo "Installazione annullata."
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi
SERVER_URL=$(echo "$SERVER_URL" | sed 's:/*$::')

PC_NAME=$(ask_text "Nome postazione Mac (es. MAC-UFFICIO1):" "$DEFAULT_PC")
if [ -z "$PC_NAME" ]; then
  echo "Installazione annullata."
  read -r -p "Premi Invio per chiudere..." _
  exit 1
fi
PC_NAME=$(echo "$PC_NAME" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9\-')

# Stage SENZA spazi nel path (piu affidabile per ditto/osascript)
TMP_ROOT=$(mktemp -d /tmp/eureka_install.XXXXXX)
STAGE="${TMP_ROOT}/EurekaAI.app"
mkdir -p "${STAGE}/Contents/MacOS"
mkdir -p "${STAGE}/Contents/Resources"

cat > "${STAGE}/Contents/MacOS/EurekaAI" << LAUNCH
#!/bin/bash
URL="${SERVER_URL}/?pc=${PC_NAME}"

# Monterey/Safari: la barra indirizzi NON si puo nascondere.
# Chrome/Edge/Brave in modalita --app = finestra senza barra URL.
open_app_window() {
  open -na "\$1" --args --app="\$URL" --new-window 2>/dev/null
}

if [ -d "/Applications/Google Chrome.app" ]; then
  open_app_window "Google Chrome"
elif [ -d "/Applications/Microsoft Edge.app" ]; then
  open_app_window "Microsoft Edge"
elif [ -d "/Applications/Brave Browser.app" ]; then
  open_app_window "Brave Browser"
elif [ -d "/Applications/Chromium.app" ]; then
  open_app_window "Chromium"
elif [ -d "/Applications/Safari.app" ]; then
  open -a Safari "\$URL"
  osascript -e 'display notification "Su Monterey Safari mostra sempre la barra indirizzi. Installa Google Chrome per la finestra senza barra." with title "Eureka AI"' 2>/dev/null || true
else
  open "\$URL"
fi
LAUNCH
chmod +x "${STAGE}/Contents/MacOS/EurekaAI"

cat > "${STAGE}/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>it</string>
  <key>CFBundleExecutable</key>
  <string>EurekaAI</string>
  <key>CFBundleIdentifier</key>
  <string>ai.eureka.client.mac</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>Eureka AI</string>
  <key>CFBundleDisplayName</key>
  <string>Eureka AI</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>__EUREKA_VERSION__</string>
  <key>CFBundleVersion</key>
  <string>__EUREKA_VERSION__</string>
  <key>LSMinimumSystemVersion</key>
  <string>10.13</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
PLIST

cat > "${STAGE}/Contents/Resources/eureka-config.txt" << CFG
SERVER_URL=${SERVER_URL}
PC_NAME=${PC_NAME}
CFG

xattr -cr "$STAGE" 2>/dev/null || true
xattr -dr com.apple.quarantine "$STAGE" 2>/dev/null || true

DEST="/Applications/Eureka AI.app"
INSTALLED=""

echo "Installazione in /Applicazioni (puo richiedere la password Mac)..."

# Helper shell senza spazi: eseguito con privilegi admin
HELPER="${TMP_ROOT}/install.sh"
cat > "$HELPER" << HELPER
#!/bin/bash
set -e
SRC="$STAGE"
DEST="$DEST"
rm -rf "\$DEST"
/usr/bin/ditto "\$SRC" "\$DEST"
chmod -R a+rX "\$DEST"
chmod +x "\$DEST/Contents/MacOS/EurekaAI"
# Rimuovi quarantine sull'app installata
xattr -cr "\$DEST" 2>/dev/null || true
HELPER
chmod +x "$HELPER"

# Tentativo 1: copia diretta (a volte funziona senza password)
if /usr/bin/ditto "$STAGE" "$DEST" 2>/dev/null; then
  chmod +x "$DEST/Contents/MacOS/EurekaAI" 2>/dev/null || true
  xattr -cr "$DEST" 2>/dev/null || true
  INSTALLED="$DEST"
else
  # Tentativo 2: password amministratore (obbligatorio su molti Mac)
  ADMIN_ERR=""
  if ADMIN_ERR=$(osascript <<APPLESCRIPT 2>&1
try
  do shell script "bash $(printf %q "$HELPER")" with administrator privileges
on error errMsg number errNum
  return "ERR:" & errNum & ":" & errMsg
end try
return "OK"
APPLESCRIPT
); then
    if echo "$ADMIN_ERR" | grep -q '^OK'; then
      INSTALLED="$DEST"
    else
      echo "Admin fallito: $ADMIN_ERR"
    fi
  else
    echo "Admin annullato o errore: $ADMIN_ERR"
  fi
fi

# Verifica che l'app sia davvero in /Applications
if [ -z "$INSTALLED" ] || [ ! -d "$DEST" ]; then
  # Ultimo tentativo: copia sulla Scrivania (sempre visibile) + istruzioni
  DESKTOP="${HOME}/Desktop/Eureka AI.app"
  rm -rf "$DESKTOP"
  /usr/bin/ditto "$STAGE" "$DESKTOP"
  chmod +x "$DESKTOP/Contents/MacOS/EurekaAI"
  xattr -cr "$DESKTOP" 2>/dev/null || true
  INSTALLED="$DESKTOP"
  alert "Non e stato possibile scrivere in /Applicazioni (password annullata o negata).

Ho creato «Eureka AI» sulla SCRIVANIA.

Trascinala tu in Applicazioni:
1. Apri Finder → Applicazioni
2. Trascina «Eureka AI» dalla Scrivania in Applicazioni"
else
  alert "Eureka AI e stata installata in Applicazioni.

Per il Dock: trascina l'icona dal Finder sulla barra in basso."
fi

# Pulisci stage (non l'app installata)
rm -rf "$TMP_ROOT"

echo ""
echo "Installato in: $INSTALLED"
echo "Server:        $SERVER_URL"
echo "Postazione:    $PC_NAME"
echo ""

# Mostra in Finder
osascript <<EOF 2>/dev/null || true
tell application "Finder"
  activate
  reveal POSIX file "$INSTALLED"
end tell
EOF

echo "Avvio Eureka AI..."
open "$INSTALLED"

echo ""
read -r -p "Premi Invio per chiudere..." _
