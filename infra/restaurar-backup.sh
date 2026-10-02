#!/usr/bin/env bash
# Devolve bases do Postgres a partir das cópias feitas por infra/backup-do-banco.sh.
# Guia em português simples: infra/COMO-RESTAURAR.md.
#
# Rode na VPS, em /opt/plataforma. O arquivo pode estar em backups-de-banco/ ou ter vindo do PC.
#
#   bash infra/restaurar-backup.sh --lado-a-lado ARQUIVO.dump
#       Restaura numa base nova, <base>__copia_<hora>, sem tocar no site. Serve para consultar e
#       devolver linhas à mão (uma matrícula apagada, um pagamento). Não sobrescreve nada.
#
#   bash infra/restaurar-backup.sh --trocar ARQUIVO.dump --sim-eu-quero-sobrescrever
#   bash infra/restaurar-backup.sh --trocar --todas CARIMBO --sim-eu-quero-sobrescrever
#       Põe a cópia no lugar da base viva. Restaura ao lado, confere dono e contagens, para a
#       aplicação, renomeia a base viva para <base>__antes_<hora> (sem apagar) e a cópia para
#       <base>, sobe a aplicação e confere o endereço. Se o site não abrir, desfaz as trocas e
#       sobe de novo. Sem a palavra no fim, só mostra o que faria.
#
#   bash infra/restaurar-backup.sh --vps-nova CARIMBO
#       Postgres sem as bases (VPS nova, ou ensaio): cria os papéis de papeis-<CARIMBO>.sql que
#       faltarem (senha tirada de env/<módulo>.env quando existir), cria cada base com o dono
#       certo e restaura. Base que já existe fica como está.
#
# CARIMBO é a parte do nome entre a base e o .dump: alunos_db-20261002-154728Z-825cad58ce30-2907648.dump
# tem carimbo 20261002-154728Z-825cad58ce30-2907648 (hora UTC; em Brasília, 3 horas a menos).
# Variáveis: ENDERECO (o que precisa responder 200 depois da troca), ESPERA_SAUDE (tentativas de 2 s
# esperando cada contêiner ficar saudável; 90), PLATAFORMA_DIR, PROJETO_COMPOSE, PASTA_DOS_BACKUPS.
# Nunca roda pg_restore --clean nem DROP DATABASE em base viva.

set -eu
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi
umask 077

RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"
PROJETO="${PROJETO_COMPOSE:-plataforma}"
PASTA="${PASTA_DOS_BACKUPS:-$RAIZ/backups-de-banco}"
ENDERECO="${ENDERECO:-https://meshcraft.top/}"
HORA="$(date -u +%Y%m%d%H%M%S)"

parar() { echo; echo "PAROU: $1"; exit 1; }

MODO=""; ARQUIVO=""; CARIMBO=""; TODAS=0; PALAVRA=0
while [ $# -gt 0 ]; do
  case "$1" in
    --lado-a-lado) MODO=lado ;;
    --trocar) MODO=trocar ;;
    --vps-nova) MODO=nova; CARIMBO="${2:-}"; shift ;;
    --todas) TODAS=1; CARIMBO="${2:-}"; shift ;;
    --sim-eu-quero-sobrescrever) PALAVRA=1 ;;
    -*) parar "não conheço a opção '$1'. Veja o cabeçalho deste arquivo." ;;
    *) ARQUIVO="$1" ;;
  esac
  shift
done
[ -n "$MODO" ] || { sed -n '2,29p' "$0"; exit 2; }

conteiner() {
  docker ps -q --filter "label=com.docker.compose.project=$PROJETO" \
    --filter "label=com.docker.compose.service=$1" | head -n1
}
PG="${PG_CONTAINER:-$(conteiner postgres)}"
[ -n "$PG" ] || parar "não achei o contêiner do Postgres (projeto $PROJETO)."
sql() { docker exec -i "$PG" psql -U postgres -v ON_ERROR_STOP=1 -AtX "$@"; }
existe() { [ -n "$(sql -c "SELECT 1 FROM pg_database WHERE datname = '$1'")" ]; }

# alunos_db-20261002-154728Z-<rótulo>.dump -> base alunos_db, carimbo 20261002-154728Z-<rótulo>
base_do() { basename "$1" | sed -nE 's/^([a-z0-9_]+)-([0-9]{8}-[0-9]{6}Z.*)\.dump$/\1/p'; }
carimbo_do() { basename "$1" | sed -nE 's/^([a-z0-9_]+)-([0-9]{8}-[0-9]{6}Z.*)\.dump$/\2/p'; }

ARQUIVOS=""
if [ -n "$CARIMBO" ]; then
  case "$CARIMBO" in *[!A-Za-z0-9_-]*|"") parar "carimbo '$CARIMBO' inválido." ;; esac
  for f in "$PASTA"/*-"$CARIMBO".dump; do [ -f "$f" ] && ARQUIVOS="$ARQUIVOS $f"; done
  [ -n "$ARQUIVOS" ] || parar "não achei nenhum <base>-$CARIMBO.dump em $PASTA."
else
  [ -n "$ARQUIVO" ] || parar "falta o arquivo .dump."
  [ -s "$ARQUIVO" ] || parar "o arquivo '$ARQUIVO' não existe ou está vazio."
  ARQUIVOS="$ARQUIVO"
fi
for f in $ARQUIVOS; do
  [ -n "$(base_do "$f")" ] || parar "o nome '$(basename "$f")' não segue <base>-AAAAMMDD-HHMMSSZ[...].dump; não sei de qual base ele é."
  docker exec -i "$PG" pg_restore -l < "$f" > /dev/null || parar "o arquivo '$(basename "$f")' não abre: está truncado ou corrompido."
done

if command -v flock >/dev/null 2>&1 && [ -d "$RAIZ" ]; then
  exec 9>"$RAIZ/.backup.lock"
  flock -w 900 9 || parar "um backup está rodando há mais de 15 min; tente de novo depois."
fi

dono_de() { # o dono da base viva; sem ela, <módulo>_user
  local dono
  dono="$(sql -c "SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '$1'")"
  [ -n "$dono" ] && [ "$dono" != postgres ] && { echo "$dono"; return; }
  echo "${1%_db}_user"
}

CONTAR="SELECT table_schema || '.' || table_name,
               (xpath('/row/c/text()', query_to_xml(format('SELECT count(*) AS c FROM %I.%I',
                 table_schema, table_name), false, true, '')))[1]::text
        FROM information_schema.tables
        WHERE table_type = 'BASE TABLE' AND table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY 1"

# Restaura ARQUIVO numa base nova DESTINO com dono DONO e confere: dono de todo objeto,
# o dono consegue alterar tabela (o migrate roda) e as contagens do backup.
restaurar_e_conferir() {
  local arquivo="$1" destino="$2" dono="$3" base contagens tabela erradas iguais=0 diferentes=0
  base="$(base_do "$arquivo")"
  [ -n "$(sql -c "SELECT 1 FROM pg_roles WHERE rolname = '$dono'")" ] \
    || parar "o papel '$dono' não existe neste Postgres. Numa VPS nova, use --vps-nova."
  existe "$destino" && parar "a base '$destino' já existe; nada foi tocado."
  sql -c "CREATE DATABASE \"$destino\" OWNER \"$dono\" TEMPLATE template0" > /dev/null
  sql -c "REVOKE ALL ON DATABASE \"$destino\" FROM PUBLIC" > /dev/null
  if ! docker exec -i "$PG" pg_restore -U postgres -d "$destino" --exit-on-error --single-transaction < "$arquivo"; then
    sql -c "DROP DATABASE \"$destino\"" > /dev/null || true  # só a cópia recém-criada, vazia
    parar "o pg_restore de '$(basename "$arquivo")' falhou; a cópia incompleta foi descartada e nada mais mudou."
  fi
  erradas="$(sql -d "$destino" -c "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname NOT LIKE 'pg_toast%'
        AND c.relkind IN ('r','p','v','m','S','f') AND pg_get_userbyid(c.relowner) <> '$dono'")"
  [ "$erradas" = 0 ] || parar "$erradas objetos de '$destino' não ficaram com o dono '$dono'."
  tabela="$(sql -d "$destino" -c "SELECT format('%I.%I', schemaname, tablename) FROM pg_tables
      WHERE schemaname NOT IN ('pg_catalog', 'information_schema') AND tableowner = '$dono' ORDER BY 1 LIMIT 1")"
  if [ -n "$tabela" ]; then
    printf 'BEGIN;\nSET LOCAL ROLE "%s";\nALTER TABLE %s ADD COLUMN _ensaio_da_restauracao int;\nROLLBACK;\n' "$dono" "$tabela" \
      | docker exec -i "$PG" psql -U postgres -v ON_ERROR_STOP=1 -qAtX -d "$destino" > /dev/null \
      || parar "o dono '$dono' não conseguiu alterar $tabela em '$destino': o migrate não rodaria."
  fi
  contagens="$(dirname "$arquivo")/$(carimbo_do "$arquivo").contagens.tsv"
  if [ -f "$contagens" ]; then
    while IFS="$(printf '\t')" read -r tab linhas; do
      antes="$(awk -F'\t' -v b="$base" -v t="$tab" '$1 == b && $2 == t {print $3}' "$contagens")"
      if [ "$antes" = "$linhas" ]; then iguais=$((iguais + 1))
      else diferentes=$((diferentes + 1)); echo "  CONTAGEM-DIFERENTE: $base $tab backup=${antes:-ausente} restaurado=$linhas"; fi
    done <<EOF
$(sql -F "$(printf '\t')" -d "$destino" -c "$CONTAR")
EOF
    echo "CONFERIDO: $destino dono $dono em tudo; $iguais tabelas com a contagem do backup, $diferentes diferentes"
  else
    echo "CONFERIDO: $destino dono $dono em tudo; sem arquivo de contagens ao lado do dump"
  fi
}

if [ "$MODO" = nova ]; then
  PAPEIS="$PASTA/papeis-$CARIMBO.sql"
  [ -f "$PAPEIS" ] || parar "não achei $PAPEIS (os papéis daquele backup)."
  for papel in $(sed -nE 's/^CREATE ROLE ([a-z0-9_]+);$/\1/p' "$PAPEIS"); do
    [ -n "$(sql -c "SELECT 1 FROM pg_roles WHERE rolname = '$papel'")" ] && continue
    grep -E "^(CREATE|ALTER) ROLE $papel( |;)" "$PAPEIS" | sql > /dev/null
    SENHA="$(cat "$RAIZ"/env/*.env 2>/dev/null | sed -nE "s#^[A-Z_]*DATABASE_URL=postgres(ql)?://$papel:([^@]+)@.*#\2#p" | head -n1)" || SENHA=""
    if [ -n "$SENHA" ]; then
      printf "ALTER ROLE \"%s\" PASSWORD '%s';\n" "$papel" "$SENHA" | sql > /dev/null
      echo "PAPEL: $papel criado, senha tirada de env/"
    else
      echo "PAPEL: $papel criado sem senha (ponha a do env/ antes de subir o site)"
    fi
  done
  for f in $ARQUIVOS; do
    base="$(base_do "$f")"
    if existe "$base"; then echo "JA-EXISTE: $base ficou como está (para trocar, use --trocar)"; continue; fi
    restaurar_e_conferir "$f" "$base" "${base%_db}_user"
  done
  echo "VPS-NOVA-CONCLUIDA: $CARIMBO"
  exit 0
fi

if [ "$MODO" = lado ]; then
  for f in $ARQUIVOS; do
    base="$(base_do "$f")"
    restaurar_e_conferir "$f" "${base}__copia_$HORA" "$(dono_de "$base")"
    echo "LADO-A-LADO-PRONTO: ${base}__copia_$HORA (consulte com: docker exec -it $PG psql -U postgres -d ${base}__copia_$HORA)"
  done
  exit 0
fi

# --trocar
BASES=""
for f in $ARQUIVOS; do
  base="$(base_do "$f")"
  existe "$base" || parar "a base '$base' não existe aqui; para Postgres sem as bases, use --vps-nova."
  BASES="$BASES $base"
done
echo "== VOU TROCAR:$BASES"
echo "   Tudo o que entrou nessas bases depois da hora do backup sai do site."
echo "   As bases de agora ficam guardadas como <base>__antes_$HORA (nada é apagado)."
echo "   O site fica fora do ar por alguns segundos a poucos minutos."
[ "$PALAVRA" = 1 ] || { echo; echo "ENSAIO: nada foi mudado. Para trocar, repita com --sim-eu-quero-sobrescrever no fim."; exit 0; }

for f in $ARQUIVOS; do
  base="$(base_do "$f")"
  restaurar_e_conferir "$f" "${base}__copia_$HORA" "$(dono_de "$base")"
done

PARADOS=""
for linha in $(docker ps --filter "label=com.docker.compose.project=$PROJETO" \
                 --format '{{.ID}}={{.Label "com.docker.compose.service"}}'); do
  servico="${linha#*=}"
  [ "$servico" = aplicacao ] && { PARADOS="$PARADOS ${linha%%=*}"; continue; }
  for base in $BASES; do
    case "$servico" in "${base%_db}"|"${base%_db}"-*) PARADOS="$PARADOS ${linha%%=*}" ;; esac
  done
done

desligar() {
  [ -z "$PARADOS" ] || docker stop -t 30 $PARADOS > /dev/null
  local nomes
  nomes="'$(echo $BASES | sed "s/ /','/g")'"
  for _ in 1 2 3 4 5; do
    sql -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid()
            AND datname IN ($nomes)" > /dev/null
    [ -z "$(sql -c "SELECT 1 FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname IN ($nomes) LIMIT 1")" ] && return 0
    sleep 2
  done
}

renomear() { sql -c "ALTER DATABASE \"$1\" RENAME TO \"$2\"" > /dev/null; }

site_abriu() {
  local id estado codigo
  [ -z "$PARADOS" ] || docker start $PARADOS > /dev/null
  for id in $PARADOS; do
    for _ in $(seq 1 "${ESPERA_SAUDE:-90}"); do
      estado="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$id")"
      [ "$estado" = healthy ] || [ "$estado" = running ] && break
      sleep 2
    done
    [ "$estado" = healthy ] || [ "$estado" = running ] || return 1
  done
  for _ in $(seq 1 12); do
    codigo="$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$ENDERECO" || true)"
    [ "$codigo" = 200 ] && return 0
    sleep 5
  done
  echo "O endereço $ENDERECO respondeu ${codigo:-nada}."
  return 1
}

echo "== TROCANDO"
desligar
TROCOU=1
for base in $BASES; do
  renomear "$base" "${base}__antes_$HORA" && renomear "${base}__copia_$HORA" "$base" || { TROCOU=0; break; }
done
if [ "$TROCOU" = 1 ] && site_abriu; then
  echo "TROCA-CONCLUIDA:$BASES voltaram ao backup; as de antes estão em <base>__antes_$HORA. Site respondeu 200."
  exit 0
fi

echo "== A TROCA NÃO DEU CERTO: DESFAZENDO"
desligar || true
for base in $BASES; do
  existe "${base}__antes_$HORA" || continue
  if existe "$base"; then renomear "$base" "${base}__falhou_$HORA" || true; fi
  renomear "${base}__antes_$HORA" "$base" || echo "ATENÇÃO: não consegui devolver o nome de ${base}__antes_$HORA para $base."
done
if site_abriu; then
  parar "a troca foi desfeita e o site voltou como estava. As bases restauradas ficaram em <base>__falhou_$HORA (ou __copia_$HORA) para estudo."
fi
parar "a troca foi desfeita (bases de antes no lugar), mas o site ainda não respondeu 200. Veja: docker ps; docker logs $PARADOS"
