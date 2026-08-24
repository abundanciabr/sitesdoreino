<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.5  ·  referencias antigas "ARMADILHAS §6.5" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.5 `transaction.on_commit(...)` nunca dispara no teste

**Sintoma:** o código chama `on_commit` (relay de outbox, por exemplo) e o teste jura
que nada foi publicado.
**Causa:** o `@pytest.mark.django_db` padrão embrulha cada teste numa transação que
sofre **rollback** no fim — nunca há COMMIT, então os callbacks são descartados.
**Solução:** no teste específico que precisa disso,
`@pytest.mark.django_db(transaction=True)` (sobrescreve o `pytestmark` do módulo).
**Origem:** Prompt 3b (pagamentos, PR #19).
