#!/bin/sh
# e2e/postgres-init.sh — roda uma vez, no primeiro boot do container (via
# docker-entrypoint-initdb.d). Cria um database por célula, todos sob o mesmo
# usuário "dev" (Lei 2 exige role por célula em produção; aqui é infra
# efêmera de teste local, não produção — ver e2e/esqueleto.sh).
set -e

for db in catalogo_db checkout_db pagamentos_db alunos_db; do
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    CREATE DATABASE ${db};
EOSQL
done
