# LICOES.md — leads

Específico desta célula. Transversal vai em `ARMADILHAS.md` (raiz).

## `EventoProcessado.objects.create()` sem `atomic()` quebra a transação do teste

**Sintoma:** `TransactionManagementError: An error occurred in the current
transaction` na SEGUNDA query após um `IntegrityError` esperado (o dedup por
`event_id` do R4), mesmo o `except IntegrityError` tendo capturado a exceção
certa.
**Causa:** o `except` só evita que a exceção suba — não desfaz o estado
"transação abortada" que o Postgres deixa depois de um erro dentro de uma
transação aberta. `pytest-django` embrulha cada teste em uma transação
(`@pytest.mark.django_db`); a query seguinte (mesmo que só um `.count()` de
asserção) esbarra na trava. **Isto mudou:** quando esta lição foi escrita, o
comando `consume_eventos` rodava em autocommit e a falta do savepoint só
quebrava dentro do isolamento do teste. Hoje `processar_envelope()` abre uma
transação externa de propósito (ver a lição sobre atomicidade, no fim deste
arquivo), então o savepoint interno passou a ser obrigatório **também em
produção**: sem ele, um `event_id` duplicado abortaria a transação inteira do
consumer, não só a do teste.
**Solução:** todo INSERT usado como guarda de idempotência (`try: ...create()
except IntegrityError`) precisa do próprio savepoint:

```python
try:
    with transaction.atomic():
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return False
```

**Isto generaliza:** a receita R4 em `CAMINHO-DOURADO.md` não mostra esse
`atomic()`. A explicação original dizia que isso era inofensivo em produção
"porque o consumer nunca roda dentro de uma transação externa" — **deixou de ser
verdade nesta célula**, e nunca foi uma aposta boa. Qualquer célula que testar o
handler de R4 diretamente (em vez de só via loop do Redis) já quebrava na segunda
asserção; qualquer célula que envolva o dedup numa transação (como esta agora
envolve, e por bom motivo) quebra em produção também. Ver também `ARMADILHAS.md` §4 (mesma lição, versão
transversal).
**Origem:** despacho leads/timeline, ao escrever `test_inv_leads_evento_idempotente.py`.

## Fase 0 → real: `test_superficie_da_api_ainda_nao_implementada` precisa ser desmembrado

O esqueleto tinha um teste parametrizado que esperava 501 em `/leads` E
`/leads/{id}/tags`. Ao implementar upsert real em `/leads` (mission desta
sessão), o handler de tags continuou 501 (fora de escopo) — o teste
parametrizado teve que virar dois testes: um smoke isolado para tags (ainda
501) e um arquivo novo (`test_leads_upsert.py`) para o comportamento real.
**Origem:** despacho leads/timeline.

## Dedup de evento e efeito do evento vivem na MESMA transação

**Onde:** `apps/core/handlers.py::processar_envelope()`.

**O bug (esteve em `main` até o PR desta lição):** o `create()` do `EventoProcessado`
ficava num `transaction.atomic()` que **commitava** antes de o handler rodar — o
handler estava fora do `with`. Se o handler estourasse por motivo transitório
(deadlock, conexão caída, timeout num pico), o evento já estava marcado como
processado: **toda reentrega futura caía no `except IntegrityError: return False` e era
descartada em silêncio.** Buraco permanente na história da pessoa — e a timeline é
justamente o que esta célula existe para não perder.

Demonstração crua contra o código anterior:

```
--- depois da falha ---
EventoProcessado gravado? True
--- depois da reentrega ---
processar_envelope devolveu: False
Entradas de timeline: 0
```

Repare no `False`: o dedup relatou "já processado" para um evento cujo efeito nunca
aconteceu. Nada distingue isso de um dedup legítimo — nem no log, nem no retorno.

**A estrutura correta são duas transações aninhadas.** Parece redundante e não é:

- **A externa** envolve o registro **e** o efeito, para que falhem juntos. É ela que
  faz a reentrega voltar a funcionar depois de uma falha no meio.
- **A interna** é savepoint **só** em volta do `create()` — a primeira lição deste
  arquivo, agora obrigatória também em produção (ver a correção lá em cima).

**A armadilha da correção óbvia:** mover o handler para **dentro do `try`** conserta a
atomicidade e planta um bug novo — um `IntegrityError` vindo do handler passa a ser
lido como "já processado". **Nesta célula isso não é hipótese:** `_upsert_lead()` usa
`get_or_create()` sobre a constraint `uniq_lead_site_email`, que sob corrida levanta
`IntegrityError` de verdade. O handler fica dentro do `atomic` externo mas **fora do
`try`**; guarda disso:
`tests/test_inv_leads_evento_atomico.py::test_integrityerror_do_handler_nao_e_confundido_com_evento_ja_processado`,
que colide na constraint real em vez de levantar um `IntegrityError` sintético.

**O invariante da célula tem duas metades.** `test_inv_leads_evento_idempotente.py`
guarda "nunca DUAS entradas de timeline"; `test_inv_leads_evento_atomico.py` guarda
"nunca ZERO". Entrega at-least-once só vira exatamente-uma com as duas.

**Consequência no loop do Redis (sabida, não corrigida aqui):** com a exceção
propagando para fora de `processar_envelope()`, o `r.xack(...)` do `Command.handle()`
não roda — a mensagem fica na PEL do consumer group. É o comportamento desejado (ela
*precisa* sobreviver para ser reentregue), mas a recuperação de mensagens presas
(`xautoclaim`) não existe nesta célula: hoje depende de o processo reiniciar.
*[Atualização 22/08/2026: resolvido — `reivindicar_presas()` roda a cada iteração
do loop do consumer; ver a lição seguinte.]*

**Origem:** despacho de dedup atômico, depois do mesmo conserto em `alunos` (PR #43) —
o bug era idêntico nas duas células porque as duas copiaram a receita R4.

## Reentrega de presas: a fila morta lê o PEL ANTES do `XAUTOCLAIM`

**Onde:** `apps/core/management/commands/consume_eventos.py` —
`reivindicar_presas()`, chamada por `uma_iteracao()` antes do `xreadgroup ">"`.
Convenção do lote de reentrega (mesma nas 4 células consumidoras):
`IDLE_MS_REENTREGA = 60000`, `MAX_ENTREGAS = 5`, fila morta em `<stream>.dlq`
com `motivo`/`delivery_count`/`movida_em`.

**A sutileza de ordem que não está em manual nenhum:** `XAUTOCLAIM` **incrementa
o delivery counter ao reivindicar**. Se a checagem de `MAX_ENTREGAS` viesse
depois dele, a própria reivindicação contaria como entrega — a mensagem iria à
fila morta com uma tentativa real a menos do que o PEL promete. Por isso o
descarte vem PRIMEIRO, lendo `times_delivered` direto do PEL
(`xpending_range(..., idle=IDLE_MS_REENTREGA)`), movendo quem já está em
`MAX_ENTREGAS` para o `.dlq` (payload original + os 3 campos, `XACK` na origem,
log ERROR com o event_id); só então o `XAUTOCLAIM` reivindica o resto e o
processa pelo MESMO `processar_mensagem()` das mensagens novas.

**Como testar sem esperar 60 segundos de relógio:** `XCLAIM` aceita `IDLE`
(backdata o tempo parado) e `RETRYCOUNT` (força o delivery_count do PEL). É
assim que `tests/test_inv_leads_reentrega_pel.py` fabrica, contra Redis REAL,
uma mensagem "presa há mais de 60s" e outra "na 5ª entrega" — mock de Redis
esconderia exatamente a semântica de PEL que está em teste. De quebra,
`uma_iteracao(r, block_ms=...)` existe para o teste não pagar os 5s de `block`
do loop de produção.

**Origem:** despacho leads/reentrega-pel (lote 2, 22/08/2026) — a pendência era
a linha "evento que faz o handler estourar fica pendente para sempre" do
ARMADILHAS-OPERACAO.md §9.

<!-- Linha de teste da auditoria das Ondas 3-6 (29/08/2026): este PR toca DUAS celulas de proposito, para medir se a matriz do ci-celula roda as DUAS suites. Sera fechado sem merge. -->
