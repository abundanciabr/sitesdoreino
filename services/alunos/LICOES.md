# LICOES — célula alunos

Específico desta célula. Transversal vai em `ARMADILHAS.md` (raiz).

## `pagamento.aprovado.v1` não carrega `product_id`

**Contexto:** `contracts/eventos/pagamento.aprovado.v1.json` (`data`) tem `site_id`,
`payment_id`, `order_id`, `amount_cents`, `method`, `mp_payment_id`, `customer` — sem
`product_id`. Mas `contracts/alunos.openapi.yaml` (`POST /matriculas`, reprocesso
manual) **exige** `product_id` no payload.
**Decisão:** matrícula criada pelo consumer (`apps/matriculas/handlers.py`) grava
`product_id=""`. Só o reprocesso manual (`POST /matriculas`) informa o valor real.
**Se for implementar `GET /alunos/{email}/matriculas` (hoje 501, fora de escopo desta
sessão):** o campo virá vazio para matrículas automáticas — não é bug, é o contrato
como está. Se isso incomodar, é `issue arquitetura:` para acrescentar `product_id`
(opcional, retrocompatível) ao evento — Rito de Contrato, não decisão de sessão.

## `select_for_update()` não trava linha que ainda não existe

**Onde:** `apps/matriculas/services.py::matricular()`.
**O problema:** o guarda de INV-P5 pede `select_for_update()` + `transaction.atomic()`,
mas um SELECT FOR UPDATE não tem o que travar quando a matrícula ainda não foi criada —
duas transações concorrentes podem passar pelo SELECT ao mesmo tempo e ambas tentar
INSERT.
**Solução usada:** `select_for_update()` cobre o caso "já existe" (lock de leitura);
a corrida de criação é fechada pela unicidade de `order_id` — quem perde o INSERT
recebe `IntegrityError` (dentro de um savepoint aninhado, ver `ARMADILHAS.md` §4.8) e
então faz um `select_for_update().get(...)` que bloqueia até o vencedor commitar.
**Evidência vermelho→verde:** rodada com a versão sem lock (`time.sleep` + create
direto) estourando `IntegrityError` sob duas threads — ver corpo do PR de feature
(`agent/alunos/matricula`).

## `consume_eventos.py` carrega o dedup junto (orçamento de 15 arquivos)

`processar_envelope()` e `HANDLERS` vivem dentro de
`apps/eventos/management/commands/consume_eventos.py` (não num `despacho.py`
separado) — decisão de orçamento, não de arquitetura. É testável normalmente:
`from apps.eventos.management.commands.consume_eventos import processar_envelope,
HANDLERS`. Se a célula ganhar um segundo stream/handler e o arquivo crescer, separar de
volta em `apps/eventos/despacho.py` é natural — não é dívida, é antecipação de
orçamento.

## Ponte (`apps/bridge/`) não foi tocada

Fase 0: `notificar_pontes()` continua stub vazio, sem chamada nenhuma a partir de
`apps/matriculas/`. Fora de escopo por despacho — nenhuma decisão tomada aqui além de
"não integrar".

## Documentação em PR separado do código

Este `LICOES.md` (e o §4.8 de `ARMADILHAS.md`) chegou num PR próprio
(`docs/alunos-licoes-matricula`), separado do PR de feature
(`agent/alunos/matricula`) — os dois juntos estouravam o orçamento mecânico de 15
arquivos (`ci/orcamento-de-mudanca.sh`), e a resposta certa era dividir, não pedir
label `arquitetural` para inchar o limite (ARMADILHAS.md §5.1).
