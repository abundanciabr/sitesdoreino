<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.3  ·  referencias antigas "ARMADILHAS §6.3" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.3 Comparação de data/hora falha por 3 horas

**Sintoma:** o mesmo instante "não bate" antes vs. depois de um `save()`+`fetch`.
**Causa:** o Postgres normaliza `timestamptz` para UTC ao persistir — `-03:00` vira
`+00:00` na string.
**Solução:** compare via `datetime.fromisoformat(...)`, nunca string ou dict cru.
**Origem:** Prompt 3a (pagamentos, PR #16).
