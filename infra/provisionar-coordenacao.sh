#!/usr/bin/env bash
# Prepara a coordenação pelo provisionar.yml, sem argumentos ou segredos no log.
set -eu

parar() { echo "PAROU POR SEGURANÇA: $1" >&2; exit 1; }
RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
cd "$RAIZ" 2>/dev/null || parar "plataforma ausente; confira a instalação oficial."
TRAVA_PUBLICACAO="$RAIZ/.publicacao.lock"
command -v flock >/dev/null 2>&1 || parar "flock ausente; instale util-linux antes de provisionar."
if ! [ "$TRAVA_PUBLICACAO" -ef "/proc/$$/fd/8" ]; then
  if [ ! -f "$TRAVA_PUBLICACAO" ]; then
    (umask 022; : >>"$TRAVA_PUBLICACAO") || parar "não criei a trava comum; confira as permissões da plataforma."
  fi
  exec 8<"$TRAVA_PUBLICACAO" || parar "não li a trava comum; confira as permissões."
fi
flock --exclusive 8 || parar "não obtive a trava comum; repita após o mutador terminar."
unset TRAVA_PUBLICACAO

ENV_ADMIN=env/admin.env
RECUPERACAO="$RAIZ/env/coordenacao.preparo"
conferir_preparo() {
  [ -f "$RECUPERACAO" ] && [ ! -L "$RECUPERACAO" ] \
    && [ "$(stat -c '%a' "$RECUPERACAO" 2>/dev/null)" = 600 ] \
    && [ "$(grep -c '^SENHA_DB=' "$RECUPERACAO" || true)" -eq 1 ] \
    && [ "$(grep -c '^RECIBOS_CHAVE=' "$RECUPERACAO" || true)" -eq 1 ] \
    && [ "$(grep -cE '^[A-Z_]+=' "$RECUPERACAO" || true)" -eq 2 ] \
    || parar "preparo protegido ilegível, incompleto ou permissivo; recupere env/coordenacao.preparo antes de repetir."
}
[ -f docker-compose.yml ] && [ -f "$ENV_ADMIN" ] || parar "compose ou env/admin.env ausente; provisione a administração primeiro."
for CHAVE_GATEWAY in ALUNOS_API_TOKEN TOKEN_CATALOGO; do
  [ "$(grep -c "^$CHAVE_GATEWAY=" "$ENV_ADMIN" || true)" -eq 1 ] \
    || parar "$CHAVE_GATEWAY ausente ou duplicada em env/admin.env; corrija a configuração antes de repetir."
  VALOR_GATEWAY="$(grep "^$CHAVE_GATEWAY=" "$ENV_ADMIN" | cut -d= -f2-)"
  [ -n "$VALOR_GATEWAY" ] || parar "$CHAVE_GATEWAY vazia em env/admin.env; corrija a configuração antes de repetir."
  export "$CHAVE_GATEWAY=$VALOR_GATEWAY"
done
unset CHAVE_GATEWAY VALOR_GATEWAY
docker compose ps postgres >/dev/null 2>&1 || parar "não consultei o Compose; execute versao-compose e estado-servico no canal oficial antes de repetir."
docker compose ps admin >/dev/null 2>&1 || parar "não consultei admin pelo Compose; execute versao-compose e estado-servico no canal oficial antes de repetir."
CID_INICIAL="$(docker compose ps -q admin)"
[ -n "$CID_INICIAL" ] && [ "$(docker inspect -f '{{.State.Health.Status}}' "$CID_INICIAL" 2>/dev/null)" = healthy ] \
  || parar "admin não está saudável; recupere o serviço antes de preparar o banco."
ESTADO_PUBLICACAO="$RAIZ/publicacoes-candidatos/admin.json"
if [ -e "$ESTADO_PUBLICACAO" ] || [ -L "$ESTADO_PUBLICACAO" ]; then
  [ -f "$ESTADO_PUBLICACAO" ] && [ ! -L "$ESTADO_PUBLICACAO" ] \
    || parar "registro da publicação admin inválido; reconcilie antes de provisionar."
  [ -f .env ] || parar "imagem admin não declarada em .env; reconcilie a publicação antes de provisionar."
  [ "$(grep -c '^ADMIN_IMAGE=' .env || true)" -eq 1 ] \
    || parar "ADMIN_IMAGE ausente ou duplicada; reconcilie a publicação antes de provisionar."
  ADMIN_IMAGE_ATUAL="$(grep '^ADMIN_IMAGE=' .env | cut -d= -f2-)"
  { printf '%s\n' "$ADMIN_IMAGE_ATUAL"; cat "$ESTADO_PUBLICACAO"; } | docker compose exec -T admin python -c \
    'import json,re,sys; imagem=sys.stdin.readline().strip(); d=json.load(sys.stdin); e=d.get("estado"); h=d.get("digest"); a=d.get("anterior_digest"); assert e in ("publicada","falhou") and (e!="publicada" or d.get("aceite_funcional")=="conferido") and isinstance(h,str) and re.fullmatch("sha256:[0-9a-f]{64}",h) and isinstance(a,str) and re.fullmatch("ghcr.io/abundanciabr/plataforma-admin@sha256:[0-9a-f]{64}",a) and imagem == ("ghcr.io/abundanciabr/plataforma-admin@"+h if e=="publicada" else a)' \
    >/dev/null 2>&1 \
    || parar "publicação admin em curso, incerta ou divergente; reconcilie o estado oficial antes de provisionar."
fi
psql_super() { docker compose exec -T postgres psql -X -At -v ON_ERROR_STOP=1 -U postgres; }
ler() { grep "^$1=" "$ENV_ADMIN" | cut -d= -f2-; }

for chave in COORDENACAO_DATABASE_URL COORDENACAO_IDENTIDADES COORDENACAO_RECIBOS_CHAVE; do
  [ "$(grep -c "^$chave=" "$ENV_ADMIN" || true)" -le 1 ] || parar "$chave duplicada; corrija env/admin.env antes de repetir."
done
DSN="$(ler COORDENACAO_DATABASE_URL)"
IDENTIDADES="$(ler COORDENACAO_IDENTIDADES)"
RECIBOS="$(ler COORDENACAO_RECIBOS_CHAVE)"
NOVO=0
if [ -z "$DSN" ] && [ -z "$IDENTIDADES" ] && [ -z "$RECIBOS" ]; then
  NOVO=1
elif ! printf '%s' "$DSN" | grep -qE '^postgres://coordenacao_user:[0-9a-f]{64}@postgres:5432/coordenacao_db$' \
  || ! printf '%s' "$RECIBOS" | grep -qE '^[0-9a-f]{64}$' \
  || [ -z "$IDENTIDADES" ]; then
  parar "configuração da coordenação parcial ou inválida; recupere o env anterior e repita."
fi

# A própria imagem do cliente valida a forma das identidades; nenhum token sai no log.
if [ "$NOVO" -eq 0 ]; then
  printf '%s' "$IDENTIDADES" | docker compose exec -T admin python -c \
    'import json,sys,re; d=json.load(sys.stdin); assert isinstance(d,dict); assert all(re.fullmatch("[0-9a-f]{64}", k) and isinstance(v,dict) and isinstance(v.get("id"),str) and v["id"] and all(isinstance(v.get(f),list) and all(isinstance(x,str) for x in v[f]) for f in ("papeis","coortes","celulas")) for k,v in d.items())' \
    >/dev/null 2>&1 || parar "identidades técnicas inválidas; corrija env/admin.env antes de repetir."
  if [ -e "$RECUPERACAO" ] || [ -L "$RECUPERACAO" ]; then
    conferir_preparo
    SENHA_PREPARO="$(grep '^SENHA_DB=' "$RECUPERACAO" | cut -d= -f2-)"
    RECIBOS_PREPARO="$(grep '^RECIBOS_CHAVE=' "$RECUPERACAO" | cut -d= -f2-)"
    [ "$DSN" = "postgres://coordenacao_user:$SENHA_PREPARO@postgres:5432/coordenacao_db" ] \
      && [ "$RECIBOS" = "$RECIBOS_PREPARO" ] \
      || parar "env e preparo protegido divergem; reconcilie antes de repetir sem rotacionar."
  fi
fi

PAPEL="$(printf '%s\n' "SELECT CASE WHEN rolcanlogin AND NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole AND NOT rolreplication AND NOT rolbypassrls AND NOT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid) THEN 'minimo' ELSE 'privilegiado' END FROM pg_roles WHERE rolname='coordenacao_user'" | psql_super 2>/dev/null)" \
  || parar "não consultei o papel; confira o PostgreSQL antes de repetir."
BANCO="$(printf '%s\n' "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname='coordenacao_db'" | psql_super 2>/dev/null)" \
  || parar "não consultei o banco; confira o PostgreSQL antes de repetir."
[ "$PAPEL" != privilegiado ] || parar "coordenacao_user tem privilégio excessivo; corrija o papel antes de repetir."
[ -z "$BANCO" ] || [ "$BANCO" = coordenacao_user ] || parar "coordenacao_db tem outro dono; confira o servidor correto."
if [ "$NOVO" -eq 0 ]; then
  [ "$PAPEL" = minimo ] && [ "$BANCO" = coordenacao_user ] || parar "ambiente aponta a banco ou papel ausente; recupere o provisionamento sem trocar o segredo."
else
  command -v openssl >/dev/null 2>&1 || parar "openssl ausente; instale antes de gerar segredos."
  if [ -e "$RECUPERACAO" ] || [ -L "$RECUPERACAO" ]; then
    conferir_preparo
    SENHA="$(grep '^SENHA_DB=' "$RECUPERACAO" | cut -d= -f2-)"
    RECIBOS="$(grep '^RECIBOS_CHAVE=' "$RECUPERACAO" | cut -d= -f2-)"
    printf '%s' "$SENHA" | grep -qE '^[0-9a-f]{64}$' \
      && printf '%s' "$RECIBOS" | grep -qE '^[0-9a-f]{64}$' \
      || parar "preparo anterior inválido; recupere o arquivo protegido antes de repetir."
  else
    [ -z "$PAPEL" ] && [ -z "$BANCO" ] \
      || parar "papel ou banco já existe sem credencial verificável; reconcilie a origem antes de repetir, sem rotacionar senha."
    SENHA="$(openssl rand -hex 32)" || parar "não gerei a senha; confira openssl."
    RECIBOS="$(openssl rand -hex 32)" || parar "não gerei a chave de recibos; confira openssl."
    [ ${#SENHA} -eq 64 ] && [ ${#RECIBOS} -eq 64 ] || parar "segredo incompleto; confira openssl."
    umask 077
    TEMP_SEGREDO="$(mktemp "$RECUPERACAO.tmp.XXXXXXXX")" || parar "não preparei arquivo protegido de recuperação; confira o disco."
    printf 'SENHA_DB=%s\nRECIBOS_CHAVE=%s\n' "$SENHA" "$RECIBOS" >"$TEMP_SEGREDO"
    chown --reference="$ENV_ADMIN" "$TEMP_SEGREDO" && chmod 600 "$TEMP_SEGREDO" \
      && mv "$TEMP_SEGREDO" "$RECUPERACAO" \
      || parar "não gravei o preparo protegido; confira o disco antes de repetir."
  fi
  if [ -z "$PAPEL" ]; then
    printf "CREATE ROLE coordenacao_user LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD '%s';\n" "$SENHA" \
      | psql_super >/dev/null 2>&1 || parar "não criei coordenacao_user; confira permissões do PostgreSQL."
  else
    printf "ALTER ROLE coordenacao_user PASSWORD '%s';\n" "$SENHA" \
      | psql_super >/dev/null 2>&1 || parar "não atualizei a senha do papel ainda sem env; confira o PostgreSQL."
  fi
  if [ -z "$BANCO" ]; then
    printf '%s\n' 'CREATE DATABASE coordenacao_db OWNER coordenacao_user' | psql_super >/dev/null 2>&1 \
      || parar "não criei coordenacao_db; confira o PostgreSQL."
  fi
  DSN="postgres://coordenacao_user:$SENHA@postgres:5432/coordenacao_db"
  IDENTIDADES='{}'
fi
ACESSO_CRUZADO="$(printf '%s\n' "SELECT count(*) FROM pg_database WHERE datname LIKE '%_db' AND datname <> 'coordenacao_db' AND datallowconn AND has_database_privilege('coordenacao_user', oid, 'CONNECT')" | psql_super 2>/dev/null)" \
  || parar "não conferi isolamento do papel; confira os privilégios do PostgreSQL."
[ "$ACESSO_CRUZADO" = 0 ] || parar "coordenacao_user alcança banco de outra célula; remova o privilégio antes de provisionar."
printf '%s\n' 'REVOKE ALL ON DATABASE coordenacao_db FROM PUBLIC' | psql_super >/dev/null 2>&1 \
  || parar "não fechei coordenacao_db ao público; confira o PostgreSQL."

# O preparo do esquema usa o contrato SQL já integrado na imagem da admin.
printf '%s\n' "$DSN" | docker compose exec -T admin python -c \
  'import os,sys,django; os.environ["COORDENACAO_DATABASE_URL"]=sys.stdin.readline().strip(); os.environ.setdefault("DJANGO_SETTINGS_MODULE","config.settings"); django.setup(); from apps.core.coordenacao import preparar; preparar()' >/dev/null 2>&1 \
  || parar "esquema da coordenação não foi preparado; confira a imagem admin e repita sem restaurar o banco."

BACKUP=""
if [ "$NOVO" -eq 1 ]; then
  umask 077
  BACKUP="$(mktemp "$ENV_ADMIN.bak.XXXXXXXX")" || parar "não criei cópia do env; confira o disco."
  cp -p "$ENV_ADMIN" "$BACKUP" || parar "não copiei o env; confira o disco antes de repetir."
  TEMP="$(mktemp "$ENV_ADMIN.tmp.XXXXXXXX")" || parar "não criei arquivo de troca; confira o disco."
  while IFS= read -r linha || [ -n "$linha" ]; do
    case "$linha" in
      COORDENACAO_DATABASE_URL=*|COORDENACAO_IDENTIDADES=*|COORDENACAO_RECIBOS_CHAVE=*) ;;
      *) printf '%s\n' "$linha" >>"$TEMP" ;;
    esac
  done <"$ENV_ADMIN"
  printf 'COORDENACAO_DATABASE_URL=%s\nCOORDENACAO_IDENTIDADES=%s\nCOORDENACAO_RECIBOS_CHAVE=%s\n' \
    "$DSN" "$IDENTIDADES" "$RECIBOS" >>"$TEMP"
  chown --reference="$ENV_ADMIN" "$TEMP" && chmod --reference="$ENV_ADMIN" "$TEMP" \
    || parar "não preservei dono e modo do env; recupere $BACKUP antes de repetir."
  mv -f "$TEMP" "$ENV_ADMIN" || parar "não gravei env/admin.env; recupere $BACKUP antes de repetir."
fi

admin_saudavel() {
  CID="$(docker compose ps -q admin)"
  [ -n "$CID" ] || return 1
  for tentativa in $(seq 1 60); do
    SAUDE="$(docker inspect -f '{{.State.Health.Status}}' "$CID" 2>/dev/null || true)"
    [ "$SAUDE" = healthy ] && return 0
    [ "$SAUDE" = unhealthy ] && return 1
    sleep 1
  done
  return 1
}
recuperar_admin() {
  [ -z "$BACKUP" ] || cp -p "$BACKUP" "$ENV_ADMIN" || return 1
  docker compose up -d --no-deps admin >/dev/null 2>&1 && admin_saudavel
}
if ! docker compose up -d --no-deps admin >/dev/null 2>&1 || ! admin_saudavel; then
  if recuperar_admin; then
    parar "preparo falhou; configuração anterior reativada e admin saudável. Corrija a falha de recarga antes de repetir."
  fi
  parar "preparo e recuperação falharam; confira docker compose ps admin. O env anterior está em $BACKUP; não altere o banco."
fi
if [ -e "$RECUPERACAO" ]; then
  rm -f -- "$RECUPERACAO" \
    || parar "admin saudável, mas o arquivo protegido de preparo permaneceu; remova-o pelo canal oficial antes de repetir."
fi
echo 'PRONTO: banco e esquema da coordenação preparados; identidades novas seguem sem acesso.'
