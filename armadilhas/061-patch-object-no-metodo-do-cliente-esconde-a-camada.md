<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §6 — Testes
     ID historico: §6.9  ·  referencias antigas "ARMADILHAS §6.9" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 6.9 `patch.object` no método do cliente esconde a camada onde o bug mora

**Sintoma:** suíte inteira verde, cobertura aparentemente boa — e um bug de
integração vivo há semanas exatamente no cliente HTTP.
**Causa:** `@patch.object(Cliente, "criar_pagamento_pix", return_value=...)`
substitui o **método inteiro**. Tudo abaixo dele — montagem do request, headers,
checagem de status, parsing do corpo — **nunca roda** em teste nenhum. O mock
devolve um dicionário perfeito que o código real nunca teria produzido.
**Solução:** desça o mock para o **transporte** com `respx` (já pinado em
`checkout`, `funil` e `pagamentos`: `respx==0.23.1`) — falsifique a *rede*, não o
seu próprio código:

```python
with respx.mock(assert_all_called=True) as mp:
    rota = mp.post("https://api.provedor.com/v1/recurso").mock(
        return_value=httpx.Response(401, json={"message": "invalid access token"})
    )
    resp = client.post("/api/celula/recurso", ...)   # atravessa a pilha inteira
assert rota.calls.last.request.headers["X-Idempotency-Key"] == chave
```

**Dois ganhos, não um:** além de enxergar o bug, você passa a poder afirmar coisas
sobre o **request que saiu** (headers, corpo, contagem de chamadas). O INV-P4 de
pagamentos tem uma cláusula — "toda escrita ao MP leva `X-Idempotency-Key` própria"
— que era **impossível de verificar** com mock de método: o header nem existia no
mundo do teste.
**Regra prática:** se o despacho fala em falha de integração (status, timeout,
payload torto), mock de método **não serve como evidência** — ele prova o
comportamento do mock. Verifique em qual camada o teste entra antes de confiar nele.
**Origem:** despacho 03 (pagamentos, fail-closed do Mercado Pago).
