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

## Dedup de evento e efeito do evento vivem na MESMA transação

**Onde:** `apps/eventos/management/commands/consume_eventos.py::processar_envelope()`.

**O bug (esteve em `main` até o PR desta lição):** o `create()` do `EventoProcessado`
ficava num `transaction.atomic()` que **commitava** antes de o handler rodar — o
handler estava fora do `with`. Se `matricular()` falhasse por motivo transitório
(deadlock, conexão caída, timeout num pico), o evento já estava marcado como
processado: **toda reentrega futura caía no `except IntegrityError: return` e era
descartada em silêncio.** O cliente pagou, a matrícula nunca acontece, e nada no
sistema descobre — esta célula não tem reconciliação.

**A estrutura correta são duas transações aninhadas.** Parece redundante e não é:

- **A externa** envolve o registro **e** o efeito, para que falhem juntos. É ela que
  faz a reentrega voltar a funcionar depois de uma falha no meio.
- **A interna** é savepoint **só** em volta do `create()`. Tem duas razões, e as duas
  precisam ser ditas: (1) `ARMADILHAS.md` §4.8 — sem savepoint próprio o
  `IntegrityError` do `event_id` duplicado aborta a transação inteira e a query
  seguinte estoura `TransactionManagementError`; (2) o **escopo do `except`** — ele
  precisa enxergar apenas o `IntegrityError` daquele `create()`.

**A armadilha da correção óbvia:** mover o handler para **dentro do `try`** conserta a
atomicidade e planta um bug novo — um `IntegrityError` vindo do handler (qualquer
constraint sem relação com `event_id`) passa a ser lido como "já processado" e o evento
some em silêncio. É o mesmo bug de antes, mais difícil de enxergar. Por isso o handler
fica dentro do `atomic` externo mas **fora do `try`**; guarda disso:
`tests/test_inv_p5_dedup_atomico.py::test_integrityerror_do_handler_nao_e_confundido_com_evento_ja_processado`.

**INV-P5 tem duas metades.** `test_inv_p5_matricula_lock.py` guarda "nunca DUAS"
(evento duplicado/concorrente ⇒ uma matrícula). `test_inv_p5_dedup_atomico.py` guarda
"nunca ZERO" (evento que falhou no meio ⇒ a reentrega ainda matricula). Entrega
at-least-once só vira exatamente-uma com as duas.

**Evidência vermelho→verde** (protocolo `ARMADILHAS.md` §6.1, `git stash` do handler):
sem o fix, os dois testes do guarda falham — e a demonstração crua do descarte foi
`Matriculas para order-demo: 0` depois da reentrega do mesmo evento. Com o fix, 12
testes verdes na célula.

**Consequência no loop do Redis (sabida, fora do escopo daquele despacho):** com a
exceção agora propagando para fora de `processar_envelope()`, o `r.xack(...)` do
`Command.handle()` não roda — a mensagem fica na PEL do consumer group. Isso é o
comportamento desejado (a mensagem *precisa* sobreviver para ser reentregue), mas a
recuperação de mensagens presas (`xautoclaim`) ainda não existe nesta célula: hoje
depende de o processo ser reiniciado. Despacho próprio.

**Fora desta célula:** `leads` tinha o mesmo formato de bug em
`apps/core/handlers.py::processar_envelope` na data deste PR. Não é conserto daqui —
1 PR = 1 célula (cerca de CI).

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
