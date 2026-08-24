<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.13  ·  referencias antigas "ARMADILHAS §3.13" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.13 Dois containers rodando `migrate --noinput` ao mesmo tempo, banco novo

**Sintoma:** `django.db.utils.IntegrityError: duplicate key value violates unique
constraint "pg_type_typname_nsp_index"` / `MigrationSchemaMissing: Unable to
create the django_migrations table` — um dos dois containers simplesmente morre
no boot, o outro sobe normal.
**Causa:** dois processos Django apontando pro MESMO banco recém-criado (sem a
tabela `django_migrations` ainda) rodam `migrate --noinput` em paralelo — os
dois tentam criar a tabela ao mesmo tempo, um perde a corrida e estoura. Em
compose de e2e isso aparece fácil: célula com um servidor HTTP (roda `migrate`
no `CMD` do Dockerfile) + um sidecar da MESMA célula pra outro processo (ex.:
um consumer de eventos) também herdando esse `CMD`, ambos subindo juntos.
**Solução:** só UM container migra. O outro depende dele com
`condition: service_healthy` (exige um `healthcheck:` no primeiro — checar
`/healthz` já resolve) e roda só o comando dele (`command: python manage.py
consume_eventos`), sem `migrate` embutido.
**Origem:** `e2e/docker-compose.e2e.yml` — serviço `alunos-consumer`, subindo
junto com `alunos` contra `alunos_db` recém-criado (despacho e2e/esqueleto).
