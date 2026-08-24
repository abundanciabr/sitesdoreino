<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.3  ·  referencias antigas "ARMADILHAS §4.3" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.3 `migrate` não encontra as migrations do app novo

**Sintoma:** app novo com modelo, migration criada, e o `migrate` ignora.
**Causa:** falta `apps/<novo>/migrations/__init__.py` — é **obrigatório**.
**Nota que economiza um arquivo no orçamento:** `apps/<novo>/management/commands/`
funciona **sem** `__init__.py` (namespace package — já usado em `apps/core`). O
próprio pacote do app também: `apps/core` não tem `__init__.py` e está em
`INSTALLED_APPS`.
**Conte esse arquivo no orçamento** de qualquer app novo com modelo próprio.
**Origem:** Prompt 2 (catalogo, PR #15) — confirmado de novo no despacho do quiz
(PR do Crivo): `apps/quiz/__init__.py` foi removido de propósito, só para caber no
orçamento de 15 arquivos, e `make ci` continuou verde.
