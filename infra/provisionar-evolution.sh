#!/usr/bin/env bash
# Provisiona a Evolution antes de o Compose referenciar env/evolution.env.
# Segredos nascem na VPS, nenhum servico e reiniciado e toda falha fecha o caminho.
if [ "${BASH_SOURCE[0]:-$0}" != "$0" ]; then
  echo "PAROU POR SEGURANÇA: rode este arquivo com bash, nunca com source."
  return 1 2>/dev/null || exit 1
fi

set -eu
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
ENV_EVOLUTION="env/evolution.env"
ENV_MENSAGERIA="env/mensageria.env"
ENV_REF="env/identidade.env"
TRAVA="env/.provisionar-evolution.lock"
TMP_EVOLUTION=""
TMP_MENSAGERIA=""
BACKUP_EVOLUTION=""
BACKUP_MENSAGERIA=""
ARQUIVOS_TROCADOS=0
ROLE_CRIADA=0
DB_CRIADO=0
TRAVA_ADQUIRIDA=0

parar() {
  echo
  echo "PAROU POR SEGURANÇA: $1"
  echo "Nenhum servico foi reiniciado. Corrija a causa e execute novamente."
  exit 1
}

psql_comando() {
  docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U postgres "$@"
}

restaurar_envs() {
  RESULTADO=0
  if [ -n "$BACKUP_MENSAGERIA" ]; then
    if cp -a "$BACKUP_MENSAGERIA" "$ENV_MENSAGERIA"; then
      rm -f "$BACKUP_MENSAGERIA" || RESULTADO=1
      BACKUP_MENSAGERIA=""
    else RESULTADO=1
    fi
  fi
  if [ -n "$BACKUP_EVOLUTION" ]; then
    if cp -a "$BACKUP_EVOLUTION" "$ENV_EVOLUTION"; then
      rm -f "$BACKUP_EVOLUTION" || RESULTADO=1
      BACKUP_EVOLUTION=""
    else RESULTADO=1
    fi
  elif [ -n "$TMP_EVOLUTION" ] || [ -f "$ENV_EVOLUTION" ]; then
    if ! rm -f "$ENV_EVOLUTION"; then RESULTADO=1; fi
  fi
  return "$RESULTADO"
}

desfazer_banco_novo() {
  RESULTADO=0
  if [ "$DB_CRIADO" -eq 1 ]; then
    if ! psql_comando -c "DROP DATABASE evolution_db" >/dev/null 2>&1; then RESULTADO=1; fi
  fi
  if [ "$ROLE_CRIADA" -eq 1 ]; then
    if ! psql_comando -c "DROP ROLE evolution_user" >/dev/null 2>&1; then RESULTADO=1; fi
  fi
  return "$RESULTADO"
}

encerrar() {
  CODIGO=$1
  FINAL="$CODIGO"
  if [ "$CODIGO" -ne 0 ]; then
    if [ "$ARQUIVOS_TROCADOS" -eq 1 ] && ! restaurar_envs; then
      echo "PAROU POR SEGURANÇA: a reversao dos arquivos falhou; nao reinicie Evolution nem mensageria."
      FINAL=1
    fi
    if ! desfazer_banco_novo; then
      echo "PAROU POR SEGURANÇA: a limpeza do banco ou role criados nesta tentativa falhou."
      FINAL=1
    fi
  fi
  [ -z "$TMP_EVOLUTION" ] || rm -f "$TMP_EVOLUTION" || FINAL=1
  [ -z "$TMP_MENSAGERIA" ] || rm -f "$TMP_MENSAGERIA" || FINAL=1
  if [ "$TRAVA_ADQUIRIDA" -eq 1 ]; then
    rmdir "$TRAVA" || FINAL=1
  fi
  return "$FINAL"
}

trap 'CODIGO=$?; trap - EXIT; encerrar "$CODIGO"; exit $?' EXIT

validar_segredo() {
  SEGREDO=$1
  ROTULO=$2
  [ "${#SEGREDO}" -eq 64 ] || parar "$ROTULO precisa ter exatamente 64 caracteres hexadecimais."
  case "$SEGREDO" in *[!0-9a-f]*) parar "$ROTULO contem caractere invalido." ;; esac
  UNICOS=$(printf '%s' "$SEGREDO" | fold -w1 | sort -u | wc -l)
  [ "$UNICOS" -ge 8 ] || parar "$ROTULO e previsivel demais; remova o valor fraco e execute novamente."
}

ler_chave() {
  grep -m1 "^$2=" "$1" 2>/dev/null | cut -d= -f2-
}

validar_chave_unica() {
  QUANTIDADE=$(grep -c "^$2=" "$1" 2>/dev/null || true)
  [ "$QUANTIDADE" -le 1 ] || parar "$2 aparece $QUANTIDADE vezes em $1; remova a duplicata."
}

gerar_segredo() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex 32
  elif [ -r /dev/urandom ]; then
    head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n'
  else
    return 1
  fi
}

cd "$RAIZ" 2>/dev/null || parar "nao achei $RAIZ."
[ -f docker-compose.yml ] || parar "nao achei docker-compose.yml em $RAIZ."
[ -f "$ENV_MENSAGERIA" ] || parar "nao achei $ENV_MENSAGERIA."
[ -f "$ENV_REF" ] || parar "nao achei $ENV_REF para copiar dono e permissao."
[ -w "$ENV_MENSAGERIA" ] || parar "nao consigo escrever em $ENV_MENSAGERIA."
mkdir "$TRAVA" 2>/dev/null || parar "outro provisionamento da Evolution esta em execucao."
TRAVA_ADQUIRIDA=1
docker compose ps postgres >/dev/null 2>&1 || parar "nao consegui falar com o PostgreSQL do Compose."

validar_chave_unica "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_URL
validar_chave_unica "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_TOKEN
TOKEN_MENSAGERIA=$(ler_chave "$ENV_MENSAGERIA" WHATSAPP_GATEWAY_TOKEN || true)

if [ -f "$ENV_EVOLUTION" ]; then
  validar_chave_unica "$ENV_EVOLUTION" AUTHENTICATION_API_KEY
  validar_chave_unica "$ENV_EVOLUTION" DATABASE_CONNECTION_URI
  CHAVE_API=$(ler_chave "$ENV_EVOLUTION" AUTHENTICATION_API_KEY || true)
  SENHA_DB=$(sed -n 's|^DATABASE_CONNECTION_URI=postgresql://evolution_user:\([^@]*\)@postgres:5432/evolution_db.*|\1|p' "$ENV_EVOLUTION")
  [ -z "$TOKEN_MENSAGERIA" ] || [ "$TOKEN_MENSAGERIA" = "$CHAVE_API" ] \
    || parar "a chave da mensageria diverge da Evolution; nao escolho um lado em silencio."
else
  if [ -n "$TOKEN_MENSAGERIA" ]; then CHAVE_API="$TOKEN_MENSAGERIA"
  else CHAVE_API=$(gerar_segredo) || parar "nao achei fonte criptografica para gerar a chave da API."
  fi
  SENHA_DB=$(gerar_segredo) || parar "nao achei fonte criptografica para gerar a senha do banco."
fi
validar_segredo "$CHAVE_API" "AUTHENTICATION_API_KEY"
validar_segredo "$SENHA_DB" "a senha de evolution_user"

EXISTE_ROLE=$(psql_comando -tAc "SELECT 1 FROM pg_roles WHERE rolname='evolution_user'") \
  || parar "nao consegui consultar evolution_user."
if [ -z "$EXISTE_ROLE" ]; then
  psql_comando -c "CREATE ROLE evolution_user LOGIN" >/dev/null \
    || parar "nao consegui criar evolution_user."
  ROLE_CRIADA=1
fi

EXISTE_DB=$(psql_comando -tAc "SELECT 1 FROM pg_database WHERE datname='evolution_db'") \
  || parar "nao consegui consultar evolution_db."
if [ -z "$EXISTE_DB" ]; then
  psql_comando -c "CREATE DATABASE evolution_db OWNER evolution_user" >/dev/null \
    || parar "nao consegui criar evolution_db."
  DB_CRIADO=1
else
  DONO_DB=$(psql_comando -tAc "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='evolution_db'") \
    || parar "nao consegui conferir o dono de evolution_db."
  DONO_DB=$(printf '%s' "$DONO_DB" | tr -d '[:space:]')
  [ "$DONO_DB" = "evolution_user" ] || parar "evolution_db pertence a '$DONO_DB', nao a evolution_user."
fi
psql_comando -c "REVOKE ALL ON DATABASE evolution_db FROM PUBLIC" >/dev/null \
  || parar "nao consegui fechar evolution_db ao publico."

TMP_EVOLUTION=$(mktemp "env/.evolution.env.XXXXXX") || parar "nao consegui criar o arquivo temporario da Evolution."
TMP_MENSAGERIA=$(mktemp "env/.mensageria.env.XXXXXX") || parar "nao consegui criar o arquivo temporario da mensageria."
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

VIU_URL=0
VIU_TOKEN=0
while IFS= read -r LINHA || [ -n "$LINHA" ]; do
  case "$LINHA" in
    WHATSAPP_GATEWAY_URL=*) [ "$VIU_URL" -eq 0 ] && printf '%s\n' 'WHATSAPP_GATEWAY_URL=http://evolution:8080'; VIU_URL=1 ;;
    WHATSAPP_GATEWAY_TOKEN=*) [ "$VIU_TOKEN" -eq 0 ] && printf 'WHATSAPP_GATEWAY_TOKEN=%s\n' "$CHAVE_API"; VIU_TOKEN=1 ;;
    *) printf '%s\n' "$LINHA" ;;
  esac
done < "$ENV_MENSAGERIA" > "$TMP_MENSAGERIA" || parar "nao consegui preparar o novo mensageria.env."
[ "$VIU_URL" -eq 1 ] || printf '%s\n' 'WHATSAPP_GATEWAY_URL=http://evolution:8080' >> "$TMP_MENSAGERIA"
[ "$VIU_TOKEN" -eq 1 ] || printf 'WHATSAPP_GATEWAY_TOKEN=%s\n' "$CHAVE_API" >> "$TMP_MENSAGERIA"

HASH_EVOLUTION=$(sed -n 's/^AUTHENTICATION_API_KEY=//p' "$TMP_EVOLUTION" | sha256sum | cut -d' ' -f1)
HASH_MENSAGERIA=$(sed -n 's/^WHATSAPP_GATEWAY_TOKEN=//p' "$TMP_MENSAGERIA" | sha256sum | cut -d' ' -f1)
[ "$HASH_EVOLUTION" = "$HASH_MENSAGERIA" ] || parar "os dois lados da credencial ficaram diferentes."

BACKUP_MENSAGERIA=$(mktemp "env/mensageria.env.bak.XXXXXX") || parar "nao consegui reservar o backup da mensageria."
cp -a "$ENV_MENSAGERIA" "$BACKUP_MENSAGERIA" || parar "nao consegui guardar o backup da mensageria."
if [ -f "$ENV_EVOLUTION" ]; then
  BACKUP_EVOLUTION=$(mktemp "env/evolution.env.bak.XXXXXX") || parar "nao consegui reservar o backup da Evolution."
  cp -a "$ENV_EVOLUTION" "$BACKUP_EVOLUTION" || parar "nao consegui guardar o backup da Evolution."
fi

ARQUIVOS_TROCADOS=1
mv -f "$TMP_EVOLUTION" "$ENV_EVOLUTION" || parar "nao consegui instalar $ENV_EVOLUTION."
TMP_EVOLUTION=""
mv -f "$TMP_MENSAGERIA" "$ENV_MENSAGERIA" || parar "nao consegui instalar $ENV_MENSAGERIA."
TMP_MENSAGERIA=""
for ARQUIVO in "$ENV_EVOLUTION" "$ENV_MENSAGERIA"; do
  if [ "$(stat -c '%U:%G %a' "$ARQUIVO" 2>/dev/null)" != "$(stat -c '%U:%G %a' "$ENV_REF" 2>/dev/null)" ]; then
    chown --reference="$ENV_REF" "$ARQUIVO" 2>/dev/null || parar "nao consegui ajustar o dono de $ARQUIVO."
    chmod --reference="$ENV_REF" "$ARQUIVO" 2>/dev/null || parar "nao consegui ajustar a permissao de $ARQUIVO."
  fi
done

HASH_EVOLUTION=$(sed -n 's/^AUTHENTICATION_API_KEY=//p' "$ENV_EVOLUTION" | sha256sum | cut -d' ' -f1)
HASH_MENSAGERIA=$(sed -n 's/^WHATSAPP_GATEWAY_TOKEN=//p' "$ENV_MENSAGERIA" | sha256sum | cut -d' ' -f1)
[ "$HASH_EVOLUTION" = "$HASH_MENSAGERIA" ] || parar "a verificacao final dos dois lados divergiu."

# O segredo segue por stdin de um builtin do shell. Nunca entra no argv do psql.
printf "%s\n" "ALTER ROLE evolution_user LOGIN PASSWORD '$SENHA_DB';" \
  | psql_comando >/dev/null 2>&1 \
  || parar "o PostgreSQL recusou a credencial; os dois envs foram restaurados."

ARQUIVOS_TROCADOS=0
ROLE_CRIADA=0
DB_CRIADO=0
rm -f "$BACKUP_MENSAGERIA" ${BACKUP_EVOLUTION:+"$BACKUP_EVOLUTION"} \
  || parar "nao consegui remover os backups temporarios com segredos."
BACKUP_MENSAGERIA=""
BACKUP_EVOLUTION=""
echo "PRONTO: evolution_db, evolution_user e os dois lados da credencial foram conferidos sem expor valores."
echo "A Evolution ainda nao foi adicionada ao Compose e nenhum envio foi ativado."
