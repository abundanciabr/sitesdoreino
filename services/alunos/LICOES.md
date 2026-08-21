# LICOES — célula alunos

Específico desta célula. Transversal vai em `ARMADILHAS.md` (raiz).

## `pagamento.aprovado.v1` não carrega `product_id`

**Contexto:** `contracts/eventos/pagamento.aprovado.v1.json` (`data`) tem `site_id`,
`payment_id`, `order_id`, `amount_cents`, `method`, `mp_payment_id`, `customer` — sem
`product_id`. Mas `contracts/alunos.openapi.yaml` (`POST /matriculas`, reprocesso
manual) **exige** `product_id` no payload.
**Decisão:** matrícula criada pelo consumer (`apps/matriculas/handlers.py`) grava
`product_id=""`. Só o reprocesso manual (`POST /matriculas`) informa o valor real.
**`GET /alunos/{email}/matriculas` foi implementado** (branch
`agent/alunos/listagem-matriculas`): o campo `product_id` vem vazio na resposta para
matrículas automáticas, exatamente como previsto aqui — não é bug, é o contrato como
está. Se isso incomodar, é `issue arquitetura:` para acrescentar `product_id`
(opcional, retrocompatível) ao evento — Rito de Contrato, não decisão de sessão.

## `GET /alunos/{email}/matriculas` — 404 por ausência total, não por site

**Decisão:** o endpoint devolve `404 "aluno inexistente"` quando o e-mail não tem
**nenhuma** `Matricula`, e `200` com a lista completa quando tem pelo menos uma —
mesmo que as matrículas sejam de sites/produtos diferentes. A rota não é escopada por
`site_id`: identidade do aluno é global por e-mail (já era invariante desta célula,
ver `constituicoes/AGENTS.alunos.md`), então "matrículas do aluno" significa todas,
não só as do site que está perguntando.
**Handler:** `Matricula.objects.filter(email=email).order_by("enrolled_at")` — se
`.exists()` for falso, `HttpError(404, ...)`; senão serializa a lista via
`JsonResponse(..., safe=False)`, do mesmo jeito que `createEnrollment` já bypassa
`response=` do ninja (ver ARMADILHAS.md §4.2 — não se aplica aqui porque não há status
customizado além de 200, mas o padrão de retornar `JsonResponse` direto, sem
`response=` no decorator, foi mantido por consistência com R1).
**Origem:** despacho "alunos: implementar GET /matriculas", branch
`agent/alunos/listagem-matriculas`.

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
