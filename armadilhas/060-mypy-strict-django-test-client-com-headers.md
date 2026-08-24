<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.8  ·  referencias antigas "ARMADILHAS §6.8" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.8 `mypy --strict` + `django.test.Client` com headers desempacotados

**Sintoma:** `Argument 4 ... incompatible type "**dict[str, str]"; expected "bool"`.
**Causa:** o stub do `Client` tem parâmetros nomeados tipados (`follow: bool`, …) e o
mypy não consegue casar as chaves de um dict dinâmico com eles.
**Solução:** passe os headers como kwargs explícitos
(`HTTP_X_SIGNATURE=...`, `HTTP_X_REQUEST_ID=...`) em vez de `**{...}`.
**Origem:** Prompt 3b (pagamentos, PR #19).
