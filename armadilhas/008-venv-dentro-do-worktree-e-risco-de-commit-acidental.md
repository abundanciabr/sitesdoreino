<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §3 — Ambiente (Windows, esta máquina)
     ID historico: §3.8  ·  referencias antigas "ARMADILHAS §3.8" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 3.8 `.venv` dentro do worktree é risco de commit acidental

**Causa:** o `.gitignore` das células não lista `.venv/`.
**Solução:** crie o venv **fora** do worktree (ex.: no scratchpad da sessão).
**Origem:** Prompt 3a (pagamentos, PR #16).
