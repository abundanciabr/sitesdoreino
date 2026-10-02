#!/usr/bin/env bash
# Ensaio de restauração: prova que as cópias de infra/backup-do-banco.sh voltam, num Postgres
# descartável, sem tocar no site. Roda no PC (Git Bash, com Docker) ou na VPS.
#
# Uso:
#   bash infra/ensaiar-restauracao.sh PASTA_DOS_BACKUPS [CARIMBO]
#   bash infra/ensaiar-restauracao.sh ~/Cofre-sitesdoreino/backups-de-banco
# Sem CARIMBO, usa o backup completo mais novo da pasta (o que tem .contagens.tsv e papeis-*.sql).
#
# Com contêineres próprios (projeto ensaio-restauracao), que saem no fim:
#   1. Postgres 17 vazio + restaurar-backup.sh --vps-nova CARIMBO: a VPS sumiu, tudo volta do cofre.
#   2. --trocar alunos_db pela cópia: a base de antes fica guardada e o site de mentira abre.
#   3. --trocar por uma cópia que derruba o site de mentira: a troca tem de se desfazer sozinha.
#   4. Os números do backup restaurado, sem nome de pessoa (infra/numeros-do-banco.sh).
# Termina com ENSAIO-PASSOU ou ENSAIO-FALHOU.

set -eu
if (set -o pipefail) 2>/dev/null; then set -o pipefail; fi

PASTA="${1:-}"
CARIMBO="${2:-}"
[ -n "$PASTA" ] && [ -d "$PASTA" ] || { sed -n '2,15p' "$0"; exit 2; }
PASTA="$(cd "$PASTA" && pwd)"
RESTAURAR="$(cd "$(dirname "$0")" && pwd)/restaurar-backup.sh"
if [ -z "$CARIMBO" ]; then
  CARIMBO="$(ls "$PASTA" | sed -nE 's/^([0-9]{8}-[0-9]{6}Z.*)\.contagens\.tsv$/\1/p' | sort | tail -n1)"
fi
[ -n "$CARIMBO" ] || { echo "ENSAIO-FALHOU: nenhum <carimbo>.contagens.tsv em $PASTA"; exit 1; }
[ -f "$PASTA/papeis-$CARIMBO.sql" ] || { echo "ENSAIO-FALHOU: falta papeis-$CARIMBO.sql em $PASTA"; exit 1; }
ALUNOS="$PASTA/alunos_db-$CARIMBO.dump"
[ -f "$ALUNOS" ] || { echo "ENSAIO-FALHOU: falta alunos_db-$CARIMBO.dump em $PASTA"; exit 1; }

NOME=ensaio-restauracao
PG=$NOME-pg
APP=$NOME-app
REDE=$NOME-net
PORTA="${PORTA_DO_ENSAIO:-18765}"
TMP="$(mktemp -d)"

tirar_conteineres() {
  docker rm -f "$PG" "$APP" > /dev/null 2>&1 || true
  docker network rm "$REDE" > /dev/null 2>&1 || true
}
trap 'tirar_conteineres; rm -rf "$TMP"' EXIT
tirar_conteineres  # sobra de um ensaio interrompido

FALHAS=0
passou() { echo "  OK: $1"; }
falhou() { echo "  FALHOU: $1"; FALHAS=$((FALHAS + 1)); }
sql() { docker exec -i "$PG" psql -U postgres -v ON_ERROR_STOP=1 -AtX "$@"; }
restaurar() {
  PLATAFORMA_DIR="$TMP" PROJETO_COMPOSE="$NOME" PASTA_DOS_BACKUPS="$PASTA" \
    ENDERECO="http://127.0.0.1:$PORTA/" ESPERA_SAUDE=20 bash "$RESTAURAR" "$@"
}

echo "== ENSAIO com o backup $CARIMBO de $PASTA"
docker network create "$REDE" > /dev/null
docker run -d --name "$PG" --network "$REDE" \
  --label com.docker.compose.project=$NOME --label com.docker.compose.service=postgres \
  -e POSTGRES_HOST_AUTH_METHOD=trust postgres:17 > /dev/null
for _ in $(seq 1 90); do
  docker logs "$PG" 2>&1 | grep -q "PostgreSQL init process complete" \
    && docker exec "$PG" pg_isready -U postgres -q 2> /dev/null && break
  sleep 1
done
docker exec "$PG" pg_isready -U postgres -q || { echo "ENSAIO-FALHOU: o Postgres descartável não subiu"; exit 1; }

echo
echo "== 1. VPS nova: todas as bases voltam do backup"
restaurar --vps-nova "$CARIMBO" | tee "$TMP/nova.log" || true
ESPERADAS="$(cut -f1 "$PASTA/$CARIMBO.contagens.tsv" | sort -u | wc -l)"
VOLTARAM="$(grep -c '^CONFERIDO: .* 0 diferentes$' "$TMP/nova.log" || true)"
if [ "$VOLTARAM" -ne "$ESPERADAS" ]; then
  echo "ENSAIO-FALHOU: voltaram $VOLTARAM de $ESPERADAS bases com as mesmas contagens (motivo nas linhas acima)."
  exit 1
fi
passou "$VOLTARAM de $ESPERADAS bases voltaram com dono certo e as mesmas contagens"

# O site de mentira: responde 200 na porta do ensaio e só fica saudável se alunos_db
# não tiver a tabela _quebra_o_site.
docker run -d --init --name "$APP" --network "$REDE" -p "127.0.0.1:$PORTA:8080" \
  --label com.docker.compose.project=$NOME --label com.docker.compose.service=aplicacao \
  --health-cmd "psql -h $PG -U postgres -d alunos_db -tAc \"SELECT to_regclass('public._quebra_o_site') IS NULL\" | grep -qx t" \
  --health-interval 1s --health-retries 2 --health-timeout 5s \
  postgres:17 perl -MIO::Socket::INET -e '
    my $s = IO::Socket::INET->new(LocalPort => 8080, Listen => 5, ReuseAddr => 1) or die;
    while (my $c = $s->accept) { sysread($c, my $b, 4096);
      print $c "HTTP/1.0 200 OK\r\nContent-Length: 2\r\n\r\nok"; close $c }' > /dev/null
for _ in $(seq 1 30); do
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$APP")" = healthy ] && break
  sleep 1
done

echo
echo "== 2. Troca de verdade: alunos_db volta ao backup e a de antes fica guardada"
sql -d alunos_db -c "CREATE TABLE _entrou_depois_do_backup (x int)" > /dev/null
restaurar --trocar "$ALUNOS" --sim-eu-quero-sobrescrever | tee "$TMP/trocar.log" || true
grep -q '^TROCA-CONCLUIDA:' "$TMP/trocar.log" && passou "a troca terminou e o site de mentira respondeu 200" \
  || falhou "a troca não terminou"
[ -z "$(sql -d alunos_db -c "SELECT to_regclass('public._entrou_depois_do_backup')")" ] \
  && passou "alunos_db agora é a do backup" || falhou "alunos_db ainda tem o que entrou depois do backup"
ANTES="$(sql -c "SELECT datname FROM pg_database WHERE datname LIKE 'alunos\\_db\\_\\_antes\\_%' ORDER BY 1 DESC LIMIT 1")"
[ -n "$ANTES" ] && [ -n "$(sql -d "$ANTES" -c "SELECT to_regclass('public._entrou_depois_do_backup')")" ] \
  && passou "a base de antes ficou guardada em $ANTES" || falhou "a base de antes não ficou guardada"

echo
echo "== 3. Troca que derruba o site: tem de se desfazer sozinha"
sleep 1  # o nome das bases guardadas leva a hora em segundos
sql -d alunos_db -c "SET ROLE alunos_user; CREATE TABLE _quebra_o_site (x int)" > /dev/null
QUEBRADO="$TMP/alunos_db-20000101-000000Z-quebrado.dump"
docker exec "$PG" pg_dump -U postgres -Fc -d alunos_db > "$QUEBRADO"
sql -d alunos_db -c "DROP TABLE _quebra_o_site" > /dev/null
MATRICULAS_ANTES="$(sql -d alunos_db -c "SELECT count(*) FROM matriculas_matricula")"
restaurar --trocar "$QUEBRADO" --sim-eu-quero-sobrescrever | tee "$TMP/quebrado.log" || true
grep -q '^PAROU: a troca foi desfeita e o site voltou como estava' "$TMP/quebrado.log" \
  && passou "a troca foi desfeita e o site de mentira voltou" || falhou "a troca ruim não se desfez como devia"
[ -z "$(sql -d alunos_db -c "SELECT to_regclass('public._quebra_o_site')")" ] \
  && [ "$(sql -d alunos_db -c "SELECT count(*) FROM matriculas_matricula")" = "$MATRICULAS_ANTES" ] \
  && passou "alunos_db é a mesma de antes da troca ruim ($MATRICULAS_ANTES matrículas)" \
  || falhou "alunos_db não é a mesma de antes da troca ruim"

echo
echo "== 4. Números do backup $CARIMBO (restaurado no Postgres descartável)"
PG_CONTAINER="$PG" bash "$(dirname "$RESTAURAR")/numeros-do-banco.sh"
echo "  tabelas no backup: $(wc -l < "$PASTA/$CARIMBO.contagens.tsv")"
echo "  linhas no backup: $(awk -F'\t' '{s += $3} END {print s}' "$PASTA/$CARIMBO.contagens.tsv")"

echo
if [ "$FALHAS" = 0 ]; then
  echo "ENSAIO-PASSOU: o backup $CARIMBO volta inteiro; a troca guarda a base de antes e se desfaz se o site cair."
else
  echo "ENSAIO-FALHOU: $FALHAS conferência(s) não passaram (veja FALHOU acima)."
  exit 1
fi
