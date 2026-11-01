#!/bin/bash
# =====================================================================
#  Instalador de «Deutsch Lernen» para macOS
#  Haz doble clic en este archivo (o arrástralo a Terminal y pulsa Enter).
#  Puedes volver a ejecutarlo para actualizar: tu progreso no se borra.
# =====================================================================
set -u
cd "$(dirname "$0")" || exit 1
SRC="$(pwd)/app"
BASE="$HOME/Library/Application Support/DeutschLernen"
PROG="$BASE/programa"
DATA="$BASE/datos"
APPDIR="$HOME/Applications"
APP="$APPDIR/Deutsch Lernen.app"
UV="$HOME/.local/bin/uv"

say() { printf "\n\033[1m%s\033[0m\n" "$1"; }
fail() {
  printf "\n\033[1;31m✗ %s\033[0m\n" "$1"
  printf "\nSi no sabes cómo seguir, copia este mensaje y pídeme ayuda.\n"
  printf "Pulsa Enter para cerrar…"; read -r _
  exit 1
}

clear
cat <<'EOF'

   ██████  Deutsch Lernen
   ██      Instalación (tarda 1–3 minutos)

EOF

[ -f "$SRC/server.py" ] || fail "No encuentro la carpeta «app» junto a este instalador. Descomprime el .zip completo y vuelve a probar."

# ---------------------------------------------------------------- 1. Python
say "1/4 · Preparando Python…"
PY=""
if [ "${DL_TEST_PYTHON:-}" != "" ]; then
  PY="$DL_TEST_PYTHON"
else
  if [ ! -x "$UV" ]; then
    echo "   Descargando el gestor «uv» (Astral, gratuito y de código abierto)…"
    curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null 2>&1
  fi
  if [ -x "$UV" ]; then
    "$UV" python install 3.12 >/dev/null 2>&1
    PY="$("$UV" python find 3.12 2>/dev/null)"
  fi
  # alternativa: el Python de las herramientas de Apple, si ya está instalado
  if [ -z "$PY" ] && xcode-select -p >/dev/null 2>&1 && [ -x /usr/bin/python3 ]; then
    PY="/usr/bin/python3"
  fi
fi
[ -n "$PY" ] && "$PY" -c "import sqlite3, http.server" 2>/dev/null || fail "No he podido preparar Python. Comprueba tu conexión a internet y vuelve a ejecutar el instalador."
echo "   ✓ Python listo"

# ---------------------------------------------------------------- 2. Programa
say "2/4 · Copiando la aplicación…"
mkdir -p "$BASE" "$DATA" "$APPDIR" || fail "No puedo crear las carpetas de la app."
rm -rf "$PROG"
cp -R "$SRC" "$PROG" || fail "No he podido copiar los archivos."
printf "%s" "$PY" > "$BASE/python-path"
echo "   ✓ Programa en: $PROG"
echo "   ✓ Tus datos en: $DATA"

# ---------------------------------------------------------------- 3. Tipografías
say "3/4 · Descargando tipografías (Atkinson Hyperlegible, Lexend e Instrument Serif)…"
FONTS="$PROG/static/fonts"
mkdir -p "$FONTS"
G="https://github.com/google/fonts/raw/main/ofl"
get_font() {  # $1 = url  $2 = nombre de archivo
  [ -s "$BASE/fonts-cache/$2" ] || { mkdir -p "$BASE/fonts-cache"; curl -fsSL --connect-timeout 10 --max-time 40 -o "$BASE/fonts-cache/$2" "$1" || rm -f "$BASE/fonts-cache/$2"; }
  [ -s "$BASE/fonts-cache/$2" ] && cp "$BASE/fonts-cache/$2" "$FONTS/$2"
}
get_font "$G/atkinsonhyperlegible/AtkinsonHyperlegible-Regular.ttf" "AtkinsonHyperlegible-Regular.ttf"
get_font "$G/atkinsonhyperlegible/AtkinsonHyperlegible-Bold.ttf" "AtkinsonHyperlegible-Bold.ttf"
get_font "$G/atkinsonhyperlegible/AtkinsonHyperlegible-Italic.ttf" "AtkinsonHyperlegible-Italic.ttf"
get_font "$G/lexend/Lexend%5Bwght%5D.ttf" "Lexend.ttf"
get_font "$G/instrumentserif/InstrumentSerif-Regular.ttf" "InstrumentSerif-Regular.ttf"
get_font "$G/instrumentserif/InstrumentSerif-Italic.ttf" "InstrumentSerif-Italic.ttf"
if [ -s "$FONTS/Lexend.ttf" ]; then echo "   ✓ Tipografías instaladas"; else echo "   · Sin conexión con GitHub: se usará la tipografía del sistema (Avenir Next)."; fi

# ---------------------------------------------------------------- 4. Aplicación y acceso directo
say "4/4 · Creando «Deutsch Lernen» en Aplicaciones y en el Escritorio…"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Deutsch Lernen</string>
  <key>CFBundleDisplayName</key><string>Deutsch Lernen</string>
  <key>CFBundleIdentifier</key><string>local.deutschlernen.app</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>DeutschLernen</string>
  <key>CFBundleIconFile</key><string>AppIcon</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
</dict></plist>
PLIST
cat > "$APP/Contents/MacOS/DeutschLernen" <<'LAUNCH'
#!/bin/bash
BASE="$HOME/Library/Application Support/DeutschLernen"
PY="$(cat "$BASE/python-path" 2>/dev/null)"
PORT=8765
URL="http://127.0.0.1:$PORT/"
mkdir -p "$BASE/datos"
if [ -z "$PY" ] || [ ! -x "$PY" ]; then
  osascript -e 'display dialog "Falta una parte de la instalación. Vuelve a abrir «Instalar.command»." buttons {"OK"} default button 1 with title "Deutsch Lernen"'
  exit 1
fi
if ! /usr/bin/curl -s --max-time 1 "${URL}api/ping" >/dev/null 2>&1; then
  nohup "$PY" "$BASE/programa/server.py" --port "$PORT" --auto-exit --no-browser >> "$BASE/datos/registro.log" 2>&1 &
  disown
  for _ in $(seq 1 60); do
    /usr/bin/curl -s --max-time 1 "${URL}api/ping" >/dev/null 2>&1 && break
    sleep 0.25
  done
fi
# Abrir en una ventana propia (sin pestañas ni barra de direcciones) si hay un navegador compatible
for B in "Google Chrome" "Microsoft Edge" "Brave Browser" "Arc"; do
  if [ -d "/Applications/$B.app" ] || [ -d "$HOME/Applications/$B.app" ]; then
    open -na "$B" --args --app="$URL" --window-size=1280,860 && exit 0
  fi
done
open -a Safari "$URL" 2>/dev/null || open "$URL"
LAUNCH
chmod +x "$APP/Contents/MacOS/DeutschLernen"

# icono
if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  ICONSET="$(mktemp -d)/AppIcon.iconset"; mkdir -p "$ICONSET"
  for s in 16 32 128 256 512; do
    sips -z $s $s "$PROG/static/icon.png" --out "$ICONSET/icon_${s}x${s}.png" >/dev/null 2>&1
    d=$((s * 2)); sips -z $d $d "$PROG/static/icon.png" --out "$ICONSET/icon_${s}x${s}@2x.png" >/dev/null 2>&1
  done
  iconutil -c icns "$ICONSET" -o "$APP/Contents/Resources/AppIcon.icns" >/dev/null 2>&1
fi
xattr -dr com.apple.quarantine "$APP" >/dev/null 2>&1
touch "$APP"

# acceso directo en el Escritorio
ln -sfn "$APP" "$HOME/Desktop/Deutsch Lernen"
echo "   ✓ App creada en Aplicaciones y en el Escritorio"

# icono fijo en el Dock (solo si aún no está)
if [ "${DL_TEST_PYTHON:-}" = "" ] && ! defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "Deutsch%20Lernen.app\|Deutsch Lernen.app"; then
  defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>file://${APP// /%20}/</string><key>_CFURLStringType</key><integer>15</integer></dict></dict></dict>"
  killall Dock >/dev/null 2>&1
  echo "   ✓ Añadida al Dock"
fi

say "✅ ¡Listo! Abriendo Deutsch Lernen…"
echo "   La próxima vez, ábrela desde su icono en el Dock (también está en el Escritorio y en Launchpad)."
if [ "${DL_TEST_PYTHON:-}" = "" ]; then
  # si el servidor de una versión anterior sigue abierto, reiniciarlo para cargar la nueva
  pkill -f "DeutschLernen/programa/server.py" >/dev/null 2>&1
  sleep 0.5
  open "$APP"
  sleep 2
  printf "\nYa puedes cerrar esta ventana.\n"
fi
