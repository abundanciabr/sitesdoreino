<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.7  ·  referencias antigas "ARMADILHAS §6.7" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.7 `mypy --strict` + `redis`: o ignore vai na chamada, não no import

**Sintoma:** `# type: ignore[import-untyped]` no `import redis` vira erro de "unused
ignore"; sem ele, `redis.from_url(...)` acusa `no-untyped-call`.
**Causa:** o redis-py ≥ 5 já traz `py.typed` (o import é tipado), mas a assinatura de
`from_url` não está totalmente anotada.
**Solução:** o ignore vai na linha da **chamada**.
**Origem:** Prompt 3b (pagamentos, PR #19).
