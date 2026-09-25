#!/usr/bin/env bash
# Provisiona banco e credencial da Evolution antes de o Compose referenciar
# env/evolution.env. Nenhum segredo sai da VPS e nenhum servico e reiniciado.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANCA: rode este arquivo com bash, nunca com source."
  return 1 2>/dev/null || exit 1
fi

set -eu
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

parar() {
  echo
  echo "PAROU POR SEGURANCA: $1"
  echo "Nenhum servico foi reiniciado. Confira a causa e execute novamente."
  exit 1
}

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_EVOLUTION="env/evolution.env"
ENV_MENSAGERIA="env/mensageria.env"
ENV_REF="env/identidade.env"

cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ."
[ -f docker-compose.yml ] || parar "nao achei docker-compose.yml em $RAIZ."
[ -f "$ENV_MENSAGERIA" ] || parar "nao achei $ENV_MENSAGERIA; nao ha segundo lado seguro para a credencial."
[ -f "$ENV_REF" ] || parar "nao achei $ENV_REF para copiar dono e permissao."
[ -w "$ENV_MENSAGERIA" ] || parar "nao consigo escrever em $ENV_MENSAGERIA."
docker compose ps postgres >/dev/null 2>&1 || parar "nao consegui falar com o PostgreSQL do Compose."

gerar_segredo() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

ler_chave() {
  grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-
}

validar_chave_unica() {
  QUANTIDADE=$(grep -c "^$2=" "$1" 2>/dev/null || true)
  [ "$QUANTIDADE" -le 1 ] || parar "$2 aparece $QUANTIDADE vezes em $1; corrija a duplicata antes de rotacionar."
}

validar_chave_unica "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_URL
validar_chave_unica "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_TOKEN

CHAVE_ATUAL=$(ler_chave "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_TOKEN || true)
if [ -n "$CHAVE_ATUAL" ]; then
  CHAVE_API="$CHAVE_ATUAL"
else
  CHAVE_API=$(gerar_segredo) || parar "nao achei fonte criptografica para gerar a chave da API."
fi
[ "${#CHAVE_API}" -ge 64 ] || parar "a chave existente de WhatsApp e curta demais; remova-a e execute novamente para gerar uma forte."

SENHA_DB=$(gerar_segredo) || parar "nao consegui gerar a senha do banco."
[ "${#SENHA_DB}" -ge 64 ] || parar "a senha gerada para o banco ficou curta."
SENHA_DB_ANTIGA=""
if [ -f "$ENV_EVOLUTION" ]; then
  SENHA_DB_ANTIGA=$(sed -n 's|^DATABASE_CONNECTION_URI=postgresql://evolution_user:\([^@]*\)@postgres:5432/evolution_db.*|\1|p' "$ENV_EVOLUTION")
fi

CARIMBO=$(date -u +%Y%m%dT%H%M%SZ)
TMP_EVOLUTION="env/.evolution.env.$CARIMBO.tmp"
TMP_MENSAGERIA="env/.mensageria.env.$CARIMBO.tmp"
BACKUP_EVOLUTION=""
BACKUP_MENSAGERIA="$ENV_MENSAGERIA.bak-$CARIMBO"

limpar_temporarios() { rm -f "$TMP_EVOLUTION" "$TMP_MENSAGERIA"; }
trap limpar_temporarios EXIT
umask 077

cat > "$TMP_EVOLUTION" <<ENV
SERVER_NAME=evolution
SERVER_TYPE=http
SERVER_PORT=8080
SERVER_URL=http://evolution:8080
CORS_ORIGIN=http://localhost
CORS_METHODS=GET,POST
CORS_CREDENTIALS=false
TELEMETRY_ENABLED=false
PROMETHEUS_METRICS=false
LOG_LEVEL=ERROR,WARN
LOG_COLOR=false
LOG_BAILEYS=error
DEL_INSTANCE=false
AUTHENTICATION_API_KEY=$CHAVE_API
AUTHENTICATION_EXPOSE_IN_FETCH_INSTANCES=false
DATABASE_ENABLED=true
DATABASE_PROVIDER=postgresql
DATABASE_CONNECTION_URI=postgresql://evolution_user:$SENHA_DB@postgres:5432/evolution_db?schema=public
DATABASE_CONNECTION_CLIENT_NAME=evolution_meshcraft
DATABASE_SAVE_DATA_INSTANCE=true
DATABASE_SAVE_DATA_NEW_MESSAGE=false
DATABASE_SAVE_MESSAGE_UPDATE=true
DATABASE_SAVE_DATA_CONTACTS=false
DATABASE_SAVE_DATA_CHATS=false
DATABASE_SAVE_DATA_LABELS=false
DATABASE_SAVE_DATA_HISTORIC=false
DATABASE_SAVE_IS_ON_WHATSAPP=false
CACHE_REDIS_ENABLED=true
CACHE_REDIS_URI=redis://evolution-redis:6379/0
CACHE_REDIS_PREFIX_KEY=evolution
CACHE_REDIS_SAVE_INSTANCES=false
CACHE_LOCAL_ENABLED=false
WEBSOCKET_ENABLED=false
WEBHOOK_GLOBAL_ENABLED=false
N8N_ENABLED=false
ENV

awk -v token="$CHAVE_API" '
  BEGIN { viu_url=0; viu_token=0 }
  /^WHATSAPP_GATEWAY_URL=/ { if (!viu_url++) print "WHATSAPP_GATEWAY_URL=http://evolution:8080"; next }
  /^WHATSAPP_GATEWAY_TOKEN=/ { if (!viu_token++) print "WHATSAPP_GATEWAY_TOKEN=" token; next }
  { print }
  END {
    if (!viu_url) print "WHATSAPP_GATEWAY_URL=http://evolution:8080"
    if (!viu_token) print "WHATSAPP_GATEWAY_TOKEN=" token
  }
' "$ENV_MENSAGERIA" > "$TMP_MENSAGERIA" || parar "nao consegui preparar o novo mensageria.env."

for PAR in "$TMP_EVOLUTION:AUTHENTICATION_API_KEY" "$TMP_MENSAGERIA:WHATSAPP_GATEWAY_TOKEN"; do
  ARQUIVO=${PAR%%:*}; CHAVE=${PAR#*:}
  [ "$(grep -c "^$CHAVE=" "$ARQUIVO")" -eq 1 ] || parar "$CHAVE nao ficou unica no arquivo preparado."
done
HASH_EVOLUTION=$(sed -n 's/^AUTHENTICATION_API_KEY=//p' "$TMP_EVOLUTION" | sha256sum | cut -d' ' -f1)
HASH_MENSAGERIA=$(sed -n 's/^WHATSAPP_GATEWAY_TOKEN=//p' "$TMP_MENSAGERIA" | sha256sum | cut -d' ' -f1)
[ "$HASH_EVOLUTION" = "$HASH_MENSAGERIA" ] || parar "os dois lados da credencial ficaram diferentes."

cp -a "$ENV_MENSAGERIA" "$BACKUP_MENSAGERIA" || parar "nao consegui guardar a copia de $ENV_MENSAGERIA."
if [ -f "$ENV_EVOLUTION" ]; then
  BACKUP_EVOLUTION="$ENV_EVOLUTION.bak-$CARIMBO"
  cp -a "$ENV_EVOLUTION" "$BACKUP_EVOLUTION" || parar "nao consegui guardar a copia de $ENV_EVOLUTION."
fi

restaurar_envs() {
  cp -a "$BACKUP_MENSAGERIA" "$ENV_MENSAGERIA" 2>/dev/null || true
  if [ -n "$BACKUP_EVOLUTION" ]; then cp -a "$BACKUP_EVOLUTION" "$ENV_EVOLUTION" 2>/dev/null || true
  else rm -f "$ENV_EVOLUTION"; fi
}

aplicar_senha_db() {
  SENHA=$1
  printf "%s\n" "ALTER ROLE evolution_user LOGIN PASSWORD '$SENHA';" \
    | docker compose exec -T postgres psql -U postgres >/dev/null 2>&1
}

restaurar_tudo() {
  ROTACAO_INICIADA=0
  restaurar_envs
  if [ -n "$SENHA_DB_ANTIGA" ]; then aplicar_senha_db "$SENHA_DB_ANTIGA" || true; fi
}

ROTACAO_INICIADA=0
encerrar() {
  CODIGO=$1
  limpar_temporarios
  if [ "$CODIGO" -ne 0 ] && [ "$ROTACAO_INICIADA" -eq 1 ]; then restaurar_tudo; fi
}
trap 'CODIGO=$?; encerrar "$CODIGO"; exit "$CODIGO"' EXIT

EXISTE_ROLE=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT 1 FROM pg_roles WHERE rolname='evolution_user'") \
  || parar "nao consegui consultar evolution_user."
if [ -z "$EXISTE_ROLE" ]; then
  docker compose exec -T postgres psql -U postgres -c "CREATE ROLE evolution_user LOGIN" >/dev/null \
    || parar "nao consegui criar evolution_user."
fi
ROTACAO_INICIADA=1
aplicar_senha_db "$SENHA_DB" || { restaurar_tudo; parar "nao consegui atualizar a credencial do banco; restaurei os arquivos."; }

EXISTE_DB=$(docker compose exec -T postgres psql -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='evolution_db'") \
  || { restaurar_tudo; parar "nao consegui consultar evolution_db; restaurei a credencial anterior."; }
if [ -z "$EXISTE_DB" ]; then
  docker compose exec -T postgres psql -U postgres -c "CREATE DATABASE evolution_db OWNER evolution_user" >/dev/null \
    || { restaurar_tudo; parar "nao consegui criar evolution_db; restaurei a credencial anterior."; }
fi
docker compose exec -T postgres psql -U postgres -c "REVOKE ALL ON DATABASE evolution_db FROM PUBLIC" >/dev/null \
  || { restaurar_tudo; parar "nao consegui fechar evolution_db ao publico; restaurei a credencial anterior."; }

mv -f "$TMP_EVOLUTION" "$ENV_EVOLUTION" || { restaurar_tudo; parar "nao consegui instalar $ENV_EVOLUTION; restaurei a credencial anterior."; }
mv -f "$TMP_MENSAGERIA" "$ENV_MENSAGERIA" || { restaurar_tudo; parar "nao consegui instalar o segundo lado; restaurei os dois envs e a credencial anterior."; }

for ARQUIVO in "$ENV_EVOLUTION" "$ENV_MENSAGERIA"; do
  if [ "$(stat -c '%U:%G %a' "$ARQUIVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$ARQUIVO" 2>/dev/null || { restaurar_tudo; parar "nao consegui ajustar o dono de $ARQUIVO; restaurei os dois envs e a credencial anterior."; }
    chmod --reference="$ENV_REF" "$ARQUIVO" 2>/dev/null || { restaurar_tudo; parar "nao consegui ajustar a permissao de $ARQUIVO; restaurei os dois envs e a credencial anterior."; }
  fi
done

HASH_EVOLUTION=$(sed -n 's/^AUTHENTICATION_API_KEY=//p' "$ENV_EVOLUTION" | sha256sum | cut -d' ' -f1)
HASH_MENSAGERIA=$(sed -n 's/^WHATSAPP_GATEWAY_TOKEN=//p' "$ENV_MENSAGERIA" | sha256sum | cut -d' ' -f1)
[ "$HASH_EVOLUTION" = "$HASH_MENSAGERIA" ] || { restaurar_tudo; parar "a verificacao final divergiu; restaurei os dois envs e a credencial anterior."; }

ROTACAO_INICIADA=0
trap - EXIT
limpar_temporarios
echo "PRONTO: evolution_db, evolution_user e os dois lados da credencial foram conferidos sem expor valores."
echo "A Evolution ainda nao foi adicionada ao Compose e nenhum envio foi ativado."
