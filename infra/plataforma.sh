#!/bin/sh
# A instalação de manutenção fixa as ferramentas fora da candidata.
set -eu
export PLATAFORMA_DIR=/opt/plataforma
export PLATAFORMA_ENTREGAS_EXCLUSIVAS=1
PUBLICADOR=/usr/local/lib/meshcraft-publicador/atual/infra/publicar.py
if [ ! -f "$PUBLICADOR" ]; then
  echo "Publicador protegido ainda não instalado pela manutenção." >&2
  exit 1
fi
exec python3 "$PUBLICADOR" "$@"
