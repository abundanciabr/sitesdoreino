#!/usr/bin/env bash
# Recupera uma versão aprovada distinta e compatível; mantém banco e pin durável.

set -eu

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ"

# Exclusao comum no receptor; o descritor herdado precisa apontar ao mesmo inode.
TRAVA_PUBLICACAO="${PLATAFORMA_DIR:-/opt/plataforma}/.publicacao.lock"
command -v flock >/dev/null 2>&1 || { echo "ERRO: flock ausente; instale util-linux na VPS antes de publicar." >&2; exit 1; }
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || { echo "ERRO: nao criei a trava comum; confira permissoes da plataforma." >&2; exit 1; }
  fi
  exec 8<"$TRAVA_PUBLICACAO" || { echo "ERRO: nao li a trava comum; o dono deve liberar leitura sem remover o arquivo." >&2; exit 1; }
fi
flock --exclusive 8 || { echo "ERRO: nao obtive a trava comum; confira o mutador em andamento antes de repetir." >&2; exit 1; }
unset TRAVA_PUBLICACAO

if [ -z "${CELULA:-}" ] || [ -z "${VAR_TAG:-}" ] || [ -z "${TAG:-}" ]; then
  echo "PAROU POR SEGURANÇA: CELULA, VAR_TAG ou TAG chegou vazia."
  echo "Sem as três, os comandos abaixo agiriam sobre a plataforma inteira,"
  echo "ou sobre uma imagem que ninguém escolheu."
  exit 1
fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_DO_ADMIN="$RAIZ/env/admin.env"
for CHAVE_DO_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  VALOR_DO_GATEWAY=$(grep -m1 "^$CHAVE_DO_GATEWAY=" "$ENV_DO_ADMIN" | cut -d= -f2-) || VALOR_DO_GATEWAY=""
  if [ -z "$VALOR_DO_GATEWAY" ]; then
    echo "PAROU POR SEGURANÇA: $CHAVE_DO_GATEWAY está ausente ou vazia em $ENV_DO_ADMIN."
    echo "O compose exige essa chave no serviço traefik, e sem ela nenhum comando"
    echo "'docker compose' desta plataforma roda. Nada foi tocado: nenhuma imagem"
    echo "subiu e a célula continua onde estava."
    echo "O QUE FAZER: escreva a linha $CHAVE_DO_GATEWAY=<o valor> em $ENV_DO_ADMIN,"
    echo "na VPS, e dispare o rollback de novo. O valor não se descobre daqui, e"
    echo "este script nunca o imprime."
    exit 1
  fi
  export "$CHAVE_DO_GATEWAY=$VALOR_DO_GATEWAY"
done
unset VALOR_DO_GATEWAY

if [ -f "$RAIZ/publicacoes/imagens.json" ]; then
  export COMPOSE_FILE="$RAIZ/docker-compose.yml:$RAIZ/publicacoes/imagens.json"
fi
python3 "$RAIZ/publicacao-local.py" recuperar
echo "REVERSAO-CONCLUIDA: $CELULA -> $TAG"
