---
schema_version: 2
armadilha: 551
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
gatilho:
  - e2e/appmax_sandbox.js
sinal:
  - "referência vazia"
guarda:
  tipo: nenhum
  motivo: "resumo() em e2e/appmax_sandbox.js documenta e testa o proprio pedido do checkout (linha 477: 'o script leva so o resumo do pedido'); ensinar o e2e a tambem publicar sha256(str(sessao.id)) exigiria expor a sessao de pagamento no lado do navegador, que e exatamente o dado que o design atual evita vazar, mudanca de escopo fora do alcance de uma entrada de licao"
licao: "e2e/appmax_sandbox.js loga resumo(pedido) = sha256(order_pk)[:16], o pedido do CHECKOUT. As operacoes da VPS usam sha256(str(sessao.id))[:16], a chave de idempotencia de PAGAMENTOS (api.py:400). Sao hashes de valores diferentes; o log do e2e nao serve de --referencia. Para achar a referencia certa, use appmax-inbox-latencia (vazio) ou appmax-pendentes."
---

# 551: `e2e/appmax_sandbox.js` loga o resumo do pedido, não a referência de idempotência que a VPS espera

**Data:** 27/09/2026 · **Onde:** `e2e/appmax_sandbox.js`,
`services/checkout/apps/core/api.py:400`, `ci/operacoes_vps.py`, obra
Appmax · **Custo evitado:** rodar `operacoes-vps.yml` com `--referencia`
copiada do log do e2e e receber "referência vazia" ou dado de outro pedido,
achando que a operação da VPS está com defeito.

## Sintoma

O log do `e2e/appmax_sandbox.js` traz, para cada caso de cartão, um resumo
de 16 caracteres hex (por exemplo em `pedido: resumo(compra.pedido)`).
Usar esse valor como `--referencia` de uma operação `appmax-pix`,
`appmax-inbox-latencia`, `appmax-pix-pedido` ou `appmax-pix-aviso` no
`operacoes-vps.yml` não encontra o registro esperado.

## Causa

```js
function resumo(id) {
  return crypto.createHash("sha256").update(String(id)).digest("hex").slice(0, 16);
}
...
pedido: compra.pedido ? resumo(compra.pedido) : null,
```

`resumo()` no e2e recebe `compra.pedido` — o identificador do **pedido do
checkout** (`order_pk`) — e devolve `sha256(order_pk)[:16]`.

As operações da VPS, por outro lado, referenciam a transação de pagamento
pela **chave de idempotência** que `services/checkout/apps/core/api.py:400`
envia à Appmax:

```python
idempotency_key=str(sessao.id),  # Mesma sessão ⇒ mesma chave [INV-P4]
```

e `ci/operacoes_vps.py` compara essa mesma chave como
`sha256(str(sessao.id))[:16]` ao consultar `appmax-pix`,
`appmax-inbox-latencia` etc. `order_pk` (pedido do checkout) e `sessao.id`
(sessão de pagamento) são valores diferentes; seus hashes truncados também
são, e o log do e2e nunca calcula o segundo.

## Solução

Não use o resumo de `pedido` do log do e2e como `--referencia` de uma
operação da VPS. Para achar a referência correta de um cartão testado:

1. Rode `appmax-inbox-latencia` com `--referencia` vazio para descoberta
   histórica (lista candidatas recentes), ou
2. Rode `appmax-pendentes`, que lista pendências sem exigir a referência de
   antemão.

Confirme a referência encontrada antes de repetir a consulta com
`--referencia` preenchido.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026; `e2e/appmax_sandbox.js`
linhas 101-102 e 715; `services/checkout/apps/core/api.py:400`;
`ci/operacoes_vps.py`.
