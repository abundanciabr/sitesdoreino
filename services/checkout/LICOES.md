# LIÇÕES — célula checkout

Documento vivo, versionado. Objetivo: qualquer agente que abrir uma sessão dentro de
`services/checkout/` lê isto em 1 minuto e não perde tempo redescobrindo o que segue.
Acrescente ao encontrar algo novo; não reescreva o que já está registrado.

## Sessão: páginas dados/pix/cartão (R6) + consumer de status (R4)

### Decisão: consumer R4 idempotente por estado, não por `EventoProcessado`

O receituário R4 canônico (`CAMINHO-DOURADO.md`) usa uma tabela `EventoProcessado`
(unicidade por `event_id`) como camada de dedup ANTES de chamar o handler. Nesta
célula o consumer (`apps/pedidos/management/commands/consume_eventos.py`) **não**
tem essa tabela — a idempotência vem do próprio handler:

```python
Order.objects.filter(pk=order_id, site_id=site_id, status=Order.AGUARDANDO).update(status=novo)
```

`Order.status` só sai de `aguardando_pagamento` uma vez; reentrega do mesmo evento
(garantia at-least-once do transporte) ou um evento atrasado e fora de ordem viram
`UPDATE` de zero linhas — no-op, sem tabela extra, sem migration extra.

**Por quê:** o orçamento mecânico do PR (≤15 arquivos) fechava em 16 com a tabela
`EventoProcessado` (modelo + migration) *e* com este próprio LICOES.md — os dois são
exigidos pelo despacho ao mesmo tempo. Perguntado, o mantenedor escolheu a
idempotência por estado em vez de dividir o despacho em dois PRs (a alternativa de
manter `EventoProcessado` e sinalizar o estouro também estava na mesa). Ver
`test_evento_reentregue_nao_reabre_a_maquina_de_estado` em
`tests/test_inv_p7_status_servidor.py` — evidência de que reentrega e fora-de-ordem
não regridem o status.

**Se a célula crescer para eventos onde o handler NÃO tem estado natural
idempotente** (ex.: um evento que dispara envio de e-mail, sem tabela de destino
única) — este atalho não serve. Volte ao receituário R4 com `EventoProcessado`.

### Auth do próprio front para a API interna: `TOKENS_ACEITOS_PAGINAS`

`contracts/checkout.openapi.yaml` exige Bearer em toda a API, e a doutrina diz que
"esta API... é usada pelas próprias páginas da célula". Como um browser público
obtém esse token não está resolvido em nenhum documento — não há sessão de usuário,
só o padrão CONV de um token estático por par consumidor
(`TOKENS_ACEITOS_<NOME>`).

Solução adotada: um novo par consumidor `paginas` (`TOKENS_ACEITOS_PAGINAS`), lido
no ponto de uso em `apps/pedidos/views.py` (não fail-hard em `settings.py` — sem o
env, as páginas ainda renderizam, só a chamada à API volta 401) e embutido no HTML
via `json_script` para `api.js` mandar como `Authorization: Bearer`.

**Isso expõe o token no HTML da página** (qualquer visitante vê via "ver código-fonte").
Aceitável apenas porque: (1) as invariantes de dinheiro (INV-P1/P2) já impedem que o
payload manipule preço mesmo com o token em mãos; (2) INV-P11 já escopa tudo por
site. Ainda assim, é um token *diferente* dos tokens servidor-a-servidor
(`TOKENS_ACEITOS_CHECKOUT` etc.) — nunca reuse o mesmo valor, porque um vazamento do
token de página não deveria comprometer o consumidor servidor-a-servidor.
**Registrado como pendência de arquitetura**, não como decisão fechada: o mantenedor
pode preferir um esquema de token de curto prazo emitido por sessão em vez de um
segredo estático público. Ver `arquivos/painel-fundacao.html`.

### Sem `base_mobile.html`

A receita R6 usa `{% extends "base_mobile.html" %}`, mas nenhuma célula da
plataforma tinha construído páginas ainda — não havia base para herdar. Cada
template (`dados.html`/`pix.html`/`cartao.html`) ficou autocontido (HTML +
`<style>` inline duplicado), para não gastar mais um arquivo do orçamento com uma
base que só esta célula usaria. Se uma segunda leva de páginas desta célula
precisar do mesmo CSS, vale extrair `templates/checkout/base_mobile.html` — não é
regra de outra célula, é decisão local de `Lei 7` (cada célula tem a sua).

### `TEMPLATES`/`STATICFILES_DIRS` não existiam em `settings.py`

Até esta sessão a célula só servia JSON (django-ninja) — não havia motor de
templates configurado. Qualquer célula que for adicionar páginas pela primeira vez
precisa acrescentar o bloco `TEMPLATES` (`DjangoTemplates`, `DIRS: [BASE_DIR /
"templates"]`) e `STATICFILES_DIRS = [BASE_DIR / "static"]` — `STATIC_URL` e
`STATIC_ROOT` já existiam (usados só para `collectstatic` de produção), mas sem
`STATICFILES_DIRS` o `{% static %}` não acha nada no dev.

### `git diff --name-only origin/main...HEAD` só existe depois do commit

Rodei o diff contra `origin/main` antes de commitar qualquer coisa e ele voltou 0
arquivos — óbvio em retrospecto (branch sem commit próprio ainda não diverge), mas
custou uma checagem extra. Confirme o orçamento DEPOIS do commit, não antes.

## Ambiente local (Windows, esta máquina) — achado nesta sessão

- **Prepender um path absoluto do Windows a `$PATH` no Git Bash quebra se você
  montar a string com o padrão `C:/Users/...`.** `export PATH="C:/Users/.../Scripts:$PATH"`
  faz o Bash splitar em `:` — o `C:` da letra da unidade vira um separador de
  campo sozinho, e o resto do path (`/Users/...`) some da procura. Sintoma:
  `python` continua resolvendo para o Python global, mesmo com o venv prependido
  primeiro, sem erro nenhum — só o binário errado sendo usado silenciosamente.
  **Solução:** converta para o estilo MSYS antes de compor o `$PATH`:
  `/c/Users/.../Scripts:$PATH` (mesma barra que o Git Bash já usa no PATH nativo
  dele). Isto é diferente da armadilha já registrada em `ARMADILHAS.md` §3.6/3.7
  (que é sobre paths *dentro* de literais de string Python) — aqui o problema é
  puramente a composição do `$PATH` do shell. **Provavelmente vale a pena
  promover isto para `ARMADILHAS.md` §3** (afeta qualquer célula que monte um
  venv de teste fora do worktree, que é a prática recomendada em §3.8) — não fiz
  a promoção nesta sessão porque o PR já estava no limite do orçamento de
  arquivos com este próprio LICOES.md contando; sinalizado no relatório final.
- Setup local completo desta sessão, para reproduzir rápido:
  ```bash
  docker run -d --name checkout-pg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
    -e POSTGRES_DB=checkout_db -p 55433:5432 postgres:17
  python -m venv <scratchpad>/venv-checkout
  <scratchpad>/venv-checkout/Scripts/python.exe -m pip install -r services/checkout/requirements.txt
  export PATH="<scratchpad-em-estilo-/c/...>/venv-checkout/Scripts:$PATH"
  export PYTHONUTF8=1 DJANGO_SECRET_KEY=ci-apenas-nunca-em-producao \
    DATABASE_URL=postgres://dev:dev@localhost:55433/checkout_db
  make ci
  ```
