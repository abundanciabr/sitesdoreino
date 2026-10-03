#!/usr/bin/env bash
# Cópia de segurança das bases do Postgres, Redis e sessão persistente da Evolution.
#
# Uso (na VPS, em /opt/plataforma):
#   bash infra/backup-do-banco.sh [ROTULO]
#   BASES="alunos_db cursos_db" bash infra/backup-do-banco.sh [ROTULO]   só as bases pedidas
#
# Chamado pelo deploy antes de trocar a versão (ROTULO = <sha12>-<pid>) e pelo
# `plataforma backup` uma vez por dia (ROTULO = diario). Grava em backups-de-banco/,
# todos com o mesmo carimbo UTC (CARIMBO = AAAAMMDD-HHMMSSZ[-ROTULO]):
#   <base>-<CARIMBO>.dump          pg_dump -Fc, só ganha o nome final depois de abrir no pg_restore -l
#   papeis-<CARIMBO>.sql           os papéis, sem senha (pg_dumpall --globals-only --no-role-passwords)
#   <CARIMBO>.contagens.tsv        base, tabela e linhas de cada tabela, contadas logo antes do dump
#   redis-<CARIMBO>.rdb            foto do Redis (falha aqui só avisa: o Redis guarda eventos de passagem)
#   evolution-instancias-<CARIMBO>.tar.gz sessão do WhatsApp Web (quando a base evolution_db está incluída)
#
# Depois de uma cópia completa, apaga os arquivos com carimbo de mais de 7 dias (o mantenedor
# escolheu guardar só os últimos 7 dias, em 02/10/2026). Sai com código diferente de zero se
# alguma base não foi copiada, e aí não apaga nada.
# Para voltar: infra/restaurar-backup.sh (guia em infra/COMO-RESTAURAR.md).

set -eu
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi
umask 077

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
PROJETO="${PROJETO_COMPOSE:-plataforma}"
PASTA="${PASTA_DOS_BACKUPS:-$RAIZ/backups-de-banco}"
ROTULO="${1:-}"
case "$ROTULO" in *[!A-Za-z0-9_-]*) echo "ERRO: rótulo '$ROTULO' com caractere fora de letra, número, - ou _." >&2; exit 2 ;; esac
CARIMBO="$(date -u +%Y%m%d-%H%M%SZ)${ROTULO:+-$ROTULO}"

falhar() { echo "BACKUP-FALHOU: $1" >&2; exit 1; }

conteiner() {
  docker ps -q --filter "label=com.docker.compose.project=$PROJETO" \
    --filter "label=com.docker.compose.service=$1" | head -n1
}
PG="${PG_CONTAINER:-$(conteiner postgres)}"
[ -n "$PG" ] || falhar "não achei o contêiner do Postgres (projeto $PROJETO). Nada foi copiado."

sql() { docker exec "$PG" psql -U postgres -v ON_ERROR_STOP=1 -AtX "$@"; }

mkdir -p "$PASTA"
if command -v flock >/dev/null 2>&1; then
  exec 9>"$RAIZ/.backup.lock"
  flock -w 900 9 || falhar "outro backup segurou a trava por mais de 15 min."
fi

TODAS="$(sql -c "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres'
                 AND datname !~ '__(copia|antes|falhou)_' ORDER BY 1")" \
  || falhar "o Postgres não respondeu à lista de bases. Nada foi copiado."
if [ -n "${BASES:-}" ]; then
  ESCOLHIDAS=""
  for BASE in $BASES; do
    if printf '%s\n' "$TODAS" | grep -qx "$BASE"; then ESCOLHIDAS="$ESCOLHIDAS $BASE"
    else echo "BACKUP: a base '$BASE' não existe neste Postgres; dispensada."; fi
  done
else
  ESCOLHIDAS="$TODAS"
fi
ESCOLHIDAS="$(echo $ESCOLHIDAS)"
if [ -z "$ESCOLHIDAS" ]; then
  echo "BACKUP-CONCLUIDO: $CARIMBO 0 bases (nenhuma base pedida existe)"
  exit 0
fi
for BASE in $ESCOLHIDAS; do
  case "$BASE" in *[!a-z0-9_]*) falhar "nome de base inesperado: '$BASE'." ;; esac
done

# Espaço: o dump fica no mesmo disco do Postgres vivo e não pode enchê-lo.
LISTA_SQL="'$(echo "$ESCOLHIDAS" | sed "s/ /','/g")'"
TAMANHO=$(sql -c "SELECT coalesce(sum(pg_database_size(datname)), 0) FROM pg_database WHERE datname IN ($LISTA_SQL)") \
  || falhar "não consegui medir o tamanho das bases."
LIVRE_KB=$(df -Pk "$PASTA" | awk 'NR==2 {print $4}')
PRECISO_KB=$(( TAMANHO / 1024 + 262144 ))
[ "$LIVRE_KB" -ge "$PRECISO_KB" ] \
  || falhar "pouco espaço em $PASTA: livres $((LIVRE_KB / 1024)) MB, preciso de $((PRECISO_KB / 1024)) MB. Nada foi copiado."

# Papéis sem senha: com eles uma VPS nova recria os donos das bases.
PAPEIS="$PASTA/papeis-$CARIMBO.sql"
docker exec "$PG" pg_dumpall -U postgres --globals-only --no-role-passwords > "$PAPEIS.parcial" \
  && [ -s "$PAPEIS.parcial" ] && mv "$PAPEIS.parcial" "$PAPEIS" \
  || { rm -f "$PAPEIS.parcial"; falhar "não consegui copiar os papéis do Postgres."; }

CONTAGENS="$PASTA/$CARIMBO.contagens.tsv"
: > "$CONTAGENS.parcial"
CONTAR="SELECT current_database(), table_schema || '.' || table_name,
               (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
                 table_schema, table_name), false, true, '')))[1]::text
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY 2"
FEITAS=0
for BASE in $ESCOLHIDAS; do
  sql -F "$(printf '\t')" -d "$BASE" -c "$CONTAR" >> "$CONTAGENS.parcial" \
    || falhar "não consegui contar as linhas de '$BASE'."
  FINAL="$PASTA/$BASE-$CARIMBO.dump"
  docker exec "$PG" pg_dump -U postgres -Fc -d "$BASE" > "$FINAL.parcial" \
    || { rm -f "$FINAL.parcial"; falhar "o pg_dump de '$BASE' falhou."; }
  [ -s "$FINAL.parcial" ] || { rm -f "$FINAL.parcial"; falhar "o dump de '$BASE' saiu vazio."; }
  docker exec -i "$PG" pg_restore -l < "$FINAL.parcial" > /dev/null \
    || { rm -f "$FINAL.parcial"; falhar "o dump de '$BASE' não abre no pg_restore."; }
  mv "$FINAL.parcial" "$FINAL"
  FEITAS=$((FEITAS + 1))
  echo "BACKUP: $BASE-$CARIMBO.dump ($(( $(wc -c < "$FINAL") / 1024 )) KB)"
done
mv "$CONTAGENS.parcial" "$CONTAGENS"

REDIS="${REDIS_CONTAINER:-$(conteiner redis)}"
if [ -n "$REDIS" ] && [ -z "${BASES:-}" ]; then
  if docker exec "$REDIS" redis-cli --rdb /tmp/backup-do-banco.rdb > /dev/null 2>&1 \
     && docker cp "$REDIS:/tmp/backup-do-banco.rdb" "$PASTA/redis-$CARIMBO.rdb" > /dev/null \
     && chmod 600 "$PASTA/redis-$CARIMBO.rdb"; then
    echo "BACKUP: redis-$CARIMBO.rdb ($(( $(wc -c < "$PASTA/redis-$CARIMBO.rdb") / 1024 )) KB)"
  else
    echo "AVISO: a foto do Redis não saiu; as bases foram copiadas."
  fi
  docker exec "$REDIS" rm -f /tmp/backup-do-banco.rdb > /dev/null 2>&1 || true
fi

# A sessão Baileys mora fora do Postgres. Ela acompanha qualquer cópia completa
# e uma cópia seletiva que inclua evolution_db; uma falha impede retenção/rotação.
if [ -z "${BASES:-}" ] || printf '%s\n' "$ESCOLHIDAS" | grep -Eq '(^|[[:space:]])evolution_db([[:space:]]|$)'; then
  INSTANCIAS="${EVOLUTION_INSTANCES_DIR:-$RAIZ/dados/evolution/instances}"
  if [ -d "$INSTANCIAS" ]; then
    SESSAO="$PASTA/evolution-instancias-$CARIMBO.tar.gz"
    tar -czf "$SESSAO.parcial" -C "$INSTANCIAS" . \
      || { rm -f "$SESSAO.parcial"; falhar "não consegui copiar a sessão persistente da Evolution."; }
    [ -s "$SESSAO.parcial" ] && tar -tzf "$SESSAO.parcial" > /dev/null \
      || { rm -f "$SESSAO.parcial"; falhar "a cópia da sessão da Evolution não abre."; }
    chmod 600 "$SESSAO.parcial" && mv "$SESSAO.parcial" "$SESSAO" \
      || { rm -f "$SESSAO.parcial"; falhar "não consegui proteger a cópia da sessão da Evolution."; }
    echo "BACKUP: evolution-instancias-$CARIMBO.tar.gz ($(( $(wc -c < "$SESSAO") / 1024 )) KB)"
  else
    echo "BACKUP: diretório de sessões da Evolution ainda não existe; nenhuma sessão presente para copiar."
  fi
fi

echo "BACKUP-CONCLUIDO: $CARIMBO $FEITAS bases em $PASTA (o carimbo é UTC; em Brasília são 3 horas a menos)"

# Só os últimos 7 dias ficam: sai todo arquivo cujo carimbo é de antes de hoje menos 7 dias (UTC).
# Só depois de uma cópia de todas as bases, para nunca sobrar apenas cópia parcial.
[ -z "${BASES:-}" ] || exit 0
LIMITE="$(date -u -d '7 days ago' +%Y%m%d)"
SAIRAM=0
for ARQ in "$PASTA"/*; do
  [ -f "$ARQ" ] || continue
  DIA="$(basename "$ARQ" | sed -nE 's/^(.*-)?([0-9]{8})-[0-9]{6}Z.*/\2/p')"
  if [ -n "$DIA" ] && [ "$DIA" -lt "$LIMITE" ]; then
    rm -f "$ARQ" && SAIRAM=$((SAIRAM + 1))
  fi
done
[ "$SAIRAM" -eq 0 ] || echo "BACKUP: saíram $SAIRAM arquivos com carimbo de antes de $LIMITE (ficam os últimos 7 dias)"
