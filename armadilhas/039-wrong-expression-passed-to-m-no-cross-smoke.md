<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.5  ·  referencias antigas "ARMADILHAS §5.5" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.5 `Wrong expression passed to '-m'` no cross-smoke

**Causa:** `IFS=' or '` em bash é um **conjunto** de separadores (espaço, `o`, `r`),
não a string `" or "`.
**Solução:** `printf '%s or ' "${MARKERS[@]}"` + strip do sufixo.
**Origem:** PR #14 — já corrigido em `ci/cross-smoke.sh`; fica registrado porque o
mesmo erro de `IFS` é fácil de repetir em qualquer script novo.
