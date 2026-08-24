<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.11  ·  referencias antigas "ARMADILHAS §3.11" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.11 `psql` num script de `docker-entrypoint-initdb.d/` conecta no banco errado

**Sintoma:** `FATAL: database "dev" does not exist` dentro do log do container
Postgres, mesmo com o container saudável e o `POSTGRES_DB` configurado.
**Causa:** `psql --username dev` **sem** `--dbname` tenta conectar num banco com o
MESMO NOME do usuário (`dev`) — comportamento padrão do cliente `psql`, não tem nada
a ver com `POSTGRES_DB` (`dev_db`), que só existe porque a imagem oficial cria esse
banco específico no boot.
**Solução:** em qualquer script de init que crie bancos adicionais (ex.: um Postgres
compartilhado por várias células num compose de e2e), passe sempre
`--dbname "$POSTGRES_DB"` explicitamente.
**Origem:** `e2e/postgres-init.sh` (despacho e2e/esqueleto — Postgres compartilhado
criando `catalogo_db`/`checkout_db`/`pagamentos_db`/`alunos_db`).
