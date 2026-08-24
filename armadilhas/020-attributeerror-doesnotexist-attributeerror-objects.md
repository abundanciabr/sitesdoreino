<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.1  ·  referencias antigas "ARMADILHAS §4.1" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.1 `AttributeError: DoesNotExist` / `AttributeError: objects`

**Sintoma:** `Session.objects` estoura `AttributeError: objects`, ou
`except Model.DoesNotExist` estoura `AttributeError: DoesNotExist` — vindo de dentro
do pydantic (`_model_construction.py`).
**Causa:** existe um `ninja.Schema` com o **mesmo nome** do model Django no mesmo
arquivo (ex.: `class Session(Schema)` e `from ...models import Session`). A classe
definida embaixo **sombreia silenciosamente** o import de cima.
**Solução:** importe o model com alias:

```python
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel
```

**Só aparece rodando os testes de verdade** — o import não falha, o lint não vê.
**Origem:** Prompt 2 (catalogo, PR #15) — e repetido em Prompt 4 (checkout), o que
mostra que a armadilha é estrutural, não distração.
