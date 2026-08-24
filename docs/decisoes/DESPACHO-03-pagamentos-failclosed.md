# DESPACHO 03 — pagamentos: falhar fechado na resposta do Mercado Pago

> ## ✅ EXECUTADO — PR #44, mergeado em 21/08/2026. NÃO redespache.
> `respx` entrou no `requirements.txt` da célula e as lições foram registradas em
> `services/pagamentos/LICOES.md`. Atenção ao efeito colateral registrado como **H7**
> em `ARMADILHAS-OPERACAO.md` §1: `POST /intents` agora devolve **502** quando o MP falha —
> comportamento correto (fail-closed), mas o checkout precisa tratar esse 502 com uma
> mensagem digna para o cliente (hoje vira erro genérico).
> **Continuam FORA (despachos próprios):** endurecimento do webhook (`data.id` +
> janela de `ts`) e `GET /v1/payments/{id}`.
>
> ~~Copie tudo abaixo da linha e cole para o agente.~~
> Criado em 21/08/2026 · merge: **humano** (CODEOWNERS — célula do dinheiro)

---

# DESPACHO — pagamentos: resposta de provedor só vira sucesso depois de validada

CÉLULA: pagamentos · WORKTREE: wt-pagamentos-failclosed · RECEITAS: R5

ANTES: leia `AGENTS.pagamentos.md`, `INVARIANTES.md` (INV-P4, INV-P8),
`services/pagamentos/LICOES.md` (inteiro — é a célula com mais armadilhas registradas) e
`ARMADILHAS.md` §4.2 (django-ninja e status ≠ 200) e §5.3 (variável nova fail-hard quebra
o CI). Declaração de abertura (RITOS.md §1) antes de tocar qualquer arquivo.

## CONTEXTO — o bug, com o código

`services/pagamentos/pagamentos/providers/mercadopago/client.py:59`:

```python
if resp.status_code >= 500:
    raise MercadoPagoError(...)
data: dict[str, Any] = resp.json()
return data
```

Qualquer **400, 401, 403, 404 ou 429** do Mercado Pago atravessa como se fosse sucesso.
E `core/gateway.py` então lê o corpo de erro como se fosse um pagamento:

```python
payment_id=str(resposta.get("id", "")),
qr_code=str(dados.get("qr_code") or ""),
```

Resultado: a intent nasce com `provider_payment_id=""` e QR vazio, e a API devolve **201
como se tivesse dado certo**. O cliente recebe uma tela de Pix com QR em branco e um botão
"copiar" que copia string vazia. Ele não consegue pagar, e **não existe caminho de reparo**
— nem endpoint, nem comando.

**Isto atinge o cartão também**: `_post` é compartilhado (`client.py:99`). No cartão é
pior — `status` vazio vira `"pending"`, que não é confirmável, e toda tentativa seguinte
devolve **409 permanente**.

**Por que os testes não pegam:** eles mockam com
`patch.object(MercadoPagoClient, "criar_pagamento_pix", ...)` — substituem o método
inteiro, então `_post` **nunca roda**. O bug mora exatamente na camada que os testes
pulam. É por isso que este despacho exige mover o mock para o transporte.

## MISSÃO

Nenhuma resposta do provedor vira sucesso interno sem validação de status HTTP **e** de
payload; e nenhuma intent incompleta é apresentada como criada.

## ALVOS (PERMITIDO ESCREVER)

- `services/pagamentos/pagamentos/providers/mercadopago/client.py`
- `services/pagamentos/pagamentos/core/gateway.py`
- `services/pagamentos/pagamentos/methods/pix/**`, `.../methods/card/**` (só o necessário)
- `services/pagamentos/pagamentos/api/intents.py`
- `services/pagamentos/tests/**`
- `services/pagamentos/requirements.txt`
- `services/pagamentos/LICOES.md`

## SOMENTE-LEITURA

`contracts/pagamentos.openapi.yaml` — **o contrato não muda neste despacho.** Se você
concluir que precisa mudar, **pare e reporte**: é Rito de Contrato (RITOS §3), não decisão
de sessão.

## FORA DE ESCOPO

- Assinatura de webhook / `data.id` / janela de `ts` — **despacho próprio**, não misture.
- `GET /v1/payments/{id}` (consultar status no MP) — despacho do webhook real na VPS.
- Qualquer outra célula. **NÃO toque em `arquivos/painel-fundacao.html`.**

## O QUE PRECISA EXISTIR

### 1. `_post` falha fechado

Qualquer status não-2xx vira `MercadoPagoError`. Distinga na mensagem: falha de
autenticação, rejeição, rate limit, indisponibilidade, timeout e **corpo que não é JSON**
(hoje `resp.json()` sobre uma página HTML de erro levanta `JSONDecodeError`, que **não** é
capturado pelo `except httpx.HTTPError` — vira 500 não tratado).

### 2. O gateway recusa traduzir resposta incompleta

Um 2xx com `id` ausente/vazio, ou Pix sem `qr_code`, **não é sucesso**. Hoje vira uma
`ResultadoPix` com campos vazios. Isso é o que produz a intent-fantasma.

### 3. A API não devolve 201 para intent incompleta

Inclui o caminho de replay: `api/intents.py` (por volta da linha 164) devolve **200 com a
intent existente** quando a chave de idempotência repete. Se essa intent tiver QR vazio,
o replay entrega o vazio de novo. Decida — e **escreva o porquê no código** — entre
recusar com erro claro ou tentar completar. Não deixe o vazio sair calado.

**[ARMADILHAS §4.2]** Não resolva status novo com `response={...}` no decorator: qualquer
valor não-`None` ali vira `ninja.Schema` dinâmico e pode vazar para `components.schemas`,
quebrando o freeze. Use `JsonResponse(dict, status=N)`.

### 4. Testes na camada de transporte (é o coração deste despacho)

Acrescente `respx==0.23.1` ao `requirements.txt` — **essa versão exata**, que já é a
pinada em `checkout` e `funil`.

Substitua o mock de método por `respx` interceptando o HTTP, e cubra: **200 feliz, 400,
401, 403, 429, 500, timeout, corpo não-JSON, e 200 com campos faltando** (`id` ausente;
Pix sem `qr_code`). Afirme também que a chamada leva o header `X-Idempotency-Key`
(INV-P4).

**Não enfraqueça** os testes existentes de INV-P4 — RITOS §2.3.

## INVARIANTES TOCADOS

INV-P4 (idempotência de intent) e INV-P8 (só `TEST-` fora da VPS; **nenhum `APP_USR-` em
lugar nenhum, nem em teste**).

Considere propor um invariante novo — *"resposta de provedor só vira sucesso interno após
validação de status e payload"* — mas **não** o adicione ao `INVARIANTES.md` neste PR:
esse arquivo é CODEOWNERS e mudá-lo junto incharia o escopo. **Proponha no handoff.**

## DoD

- Guarda **vermelho→verde** para o caso 401: hoje a criação devolve 201 com
  `provider_payment_id` vazio; depois do fix, falha alto. **Cole a saída crua dos dois
  estados.**
- Nenhum caminho devolve intent com `provider_payment_id` ou `qr_code` vazio.
- `mypy --strict` verde (a célula tem `mypy.ini`) e `lint-imports` verde (tem
  `.importlinter`) — os dois rodam no `make ci` desta célula.
- `make contrato-check` VERDE — **o contrato exportado não pode mudar**.
- `make ci` + cross-smoke VERDE — cole a saída completa, sem resumir.

## ORÇAMENTO

≤ 15 arquivos. Se estourar, **pare e avise** — não funda arquivos de teste para caber
(foi assim que a tabela de dedup do checkout e o relay Huey se perderam, e as duas viraram
dívida aberta). Prefira dividir e relatar.

## EVIDÊNCIA

Saída crua do 401 antes e depois + `make ci` + cross-smoke completos. Handoff completo ao
final (RITOS.md §1): branch, arquivos, resultado, pendências, pronto para PR ou não.
