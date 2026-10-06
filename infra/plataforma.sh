#!/bin/sh
# A instalação de manutenção fixa as ferramentas fora da candidata.
set -eu
export PLATAFORMA_DIR=/opt/plataforma
PUBLICADOR=/usr/local/lib/meshcraft-publicador/atual/infra/publicar.py
if [ ! -f "$PUBLICADOR" ]; then
  echo "Publicador protegido ainda não instalado pela manutenção." >&2
  exit 1
fi
case "${1:-}" in
  receber|publicar)
    git -C /opt/plataforma/codigo/repo.git fetch --quiet origin +refs/heads/main:refs/heads/main ;;
esac
exec python3 "$PUBLICADOR" "$@"
