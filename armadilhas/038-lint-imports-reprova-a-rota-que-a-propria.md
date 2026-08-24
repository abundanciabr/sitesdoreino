<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.4  ·  referencias antigas "ARMADILHAS §5.4" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.4 `lint-imports` reprova a rota que a própria constituição manda usar

**Sintoma:** contrato `forbidden` do import-linter acusa
`methods.pix -> core.gateway -> providers...` — exatamente o caminho aprovado.
**Causa:** `type = forbidden` checa a cadeia de imports **transitiva** por padrão.
**Solução:** `allow_indirect_imports = True` no contrato — restringe a checagem ao
import **direto**, que é o que "só fale com X através de Y" realmente significa.
**Origem:** Prompt 3a (pagamentos, PR #16).
