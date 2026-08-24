<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.2  ·  referencias antigas "ARMADILHAS §5.2" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.2 `❌ MURALHA: este PR toca N células`

**Causa:** `ci/cerca-de-celula.sh` — 1 PR = 1 célula, sem exceção. `contracts/` nunca
muda junto com `services/` (Rito de Contrato, RITOS.md §3).
**Nota útil:** arquivos de raiz e de `ci/` **não** contam como célula — dá para
corrigir um script de CI no mesmo PR sem violar a cerca (mas eles contam no
orçamento).
**Origem:** Prompt 3a (pagamentos, PR #16 — o fix do `cross-smoke.sh` entrou junto).
