#!/usr/bin/env bash
# Volta para uma versão aprovada distinta da que está no ar; o banco fica como está.

set -eu

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"
PUBLICACAO_LOCAL="${PUBLICACAO_LOCAL:-$RAIZ/publicacao-local.py}"

if [ -z "${CELULA:-}" ] || [ -z "${VAR_TAG:-}" ] || [ -z "${TAG:-}" ]; then
  echo "PAROU POR SEGURANÇA: CELULA, VAR_TAG ou TAG chegou vazia."
  echo "Sem as três, os comandos abaixo agiriam sobre a plataforma inteira,"
  echo "ou sobre uma imagem que ninguém escolheu."
  exit 1
fi

if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
  export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
fi
python3 "$PUBLICACAO_LOCAL" recuperar
echo "REVERSAO-CONCLUIDA: $CELULA -> $TAG"
