#!/bin/bash
# Desinstala «Deutsch Lernen». Te pregunta antes de borrar tu progreso.
BASE="$HOME/Library/Application Support/DeutschLernen"
pkill -f "DeutschLernen/programa/server.py" >/dev/null 2>&1
rm -rf "$HOME/Applications/Deutsch Lernen.app" "$HOME/Desktop/Deutsch Lernen" "$BASE/programa" "$BASE/fonts-cache" "$BASE/python-path"
echo "La aplicación se ha desinstalado. Si su icono sigue en el Dock, haz clic derecho sobre él → Opciones → Eliminar del Dock."
printf "¿Borrar también tu progreso y tus apuntes? Escribe «borrar» para confirmar (o pulsa Enter para conservarlos): "
read -r ans
if [ "$ans" = "borrar" ]; then
  rm -rf "$BASE"
  echo "Progreso borrado."
else
  echo "Tu progreso sigue guardado en: $BASE/datos"
fi
printf "Pulsa Enter para cerrar…"; read -r _
