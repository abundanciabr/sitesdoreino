<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.2  ·  referencias antigas "ARMADILHAS §6.2" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.2 `respx.models.AllMockedAssertionError: ... not mocked!`

**Sintoma:** o teste do caminho "recurso inexistente" estoura em vez de receber 404.
**Causa:** o `respx` só responde o que foi registrado; rota não registrada é erro, não
404. E ele resolve as rotas **na ordem de registro** — a primeira que casar ganha.
**Solução:** registre as rotas específicas primeiro e um catch-all por último:

```python
mock.get(url__regex=r".*/sites/[^/]+/ofertas/.+").mock(return_value=httpx.Response(404))
```

**Origem:** Prompt 4 (checkout).
