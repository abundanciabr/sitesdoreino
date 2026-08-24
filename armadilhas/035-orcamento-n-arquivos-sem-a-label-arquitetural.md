<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.1  ·  referencias antigas "ARMADILHAS §5.1" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.1 `❌ ORÇAMENTO: N arquivos sem a label 'arquitetural'`

**Sintoma:** o workflow `muralhas` reprova o PR.
**Causa:** `ci/orcamento-de-mudanca.sh` conta
`git diff --name-only origin/main...HEAD | wc -l`. O limite é **15**, e é mecânico —
não é autoavaliação do agente.
**Solução:** rode esse diff **antes** de abrir o PR:

```bash
git diff --name-only origin/main...HEAD | wc -l
bash ci/orcamento-de-mudanca.sh
```

Se estourou, **divida em PRs**, não peça label. Vários despachos proíbem
explicitamente usar label para inchar escopo.
**Origem:** Prompt 2 (catalogo, PR #15 — 16 arquivos, reprovado, corrigido para 15).
