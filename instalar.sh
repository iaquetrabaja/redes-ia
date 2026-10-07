#!/usr/bin/env bash
# Redes IA: instalación para Mac y Linux (solo la primera vez)
set -e
cd "$(dirname "$0")"
PY=python3
command -v $PY >/dev/null 2>&1 || { echo "No encuentro python3. Instálalo (Mac: https://www.python.org/downloads/ ; Linux: sudo apt install python3 python3-venv)"; exit 1; }
[ -d .venv ] || $PY -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip >/dev/null
python -m pip install -r requirements.txt
echo
echo "  Listo. Ahora ejecuta ./iniciar.sh"
