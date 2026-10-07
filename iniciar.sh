#!/usr/bin/env bash
# Redes IA: arranca el panel y abre el navegador (añade --demo para ver datos de ejemplo)
cd "$(dirname "$0")"
[ -d .venv ] || ./instalar.sh
. .venv/bin/activate
python -m redes_ia "$@"
