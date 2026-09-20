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

## Reentrega do PEL + fila morta: o desenho e as pegadinhas dos comandos de stream

**Onde:** `reentregar_presas()` e `_mover_para_fila_morta()` em
`apps/eventos/management/commands/consume_eventos.py`; guarda em
`tests/test_reentrega_pel.py`. Fecha o buraco medido em `ARMADILHAS-OPERACAO.md` §9:
`xreadgroup(">")` só entrega mensagem NOVA — o evento que estourava o handler
ficava em XPENDING para sempre. Convenção do lote (mesma nas 4 células
consumidoras): `IDLE_MS_REENTREGA = 60_000`, `MAX_ENTREGAS = 5`, DLQ em
`<stream>.dlq` com payload original + `motivo`/`delivery_count`/`movida_em`.

**Por que XPENDING E XAUTOCLAIM, nesta ordem:** `XAUTOCLAIM` devolve o corpo mas
NÃO a contagem de entregas; `XPENDING` (forma estendida, com filtro `idle`)
devolve a contagem mas NÃO o corpo. Então: primeiro `xpending_range` decide quem
já chegou a `MAX_ENTREGAS` → busca o corpo por `XRANGE id id`, `XADD` na `.dlq`
e `XACK` (o ACK a tira do PEL, e o `XAUTOCLAIM` seguinte já não a vê). Só depois
o `XAUTOCLAIM` reivindica o resto e reprocessa pelo MESMO `processar_envelope()`
das mensagens novas. A ordem inversa (reivindicar primeiro) incrementaria a
contagem antes da decisão e mudaria a semântica do teto.

**Semântica do teto:** cada `XAUTOCLAIM` incrementa o `delivery_count`. Uma
mensagem envenenada faz então: entrega 1 (`xreadgroup`) + reivindicações 2..5 —
cinco tentativas de processamento no total; quando o PEL mostra 5, o ciclo
seguinte a move para a `.dlq` sem rodar o handler. Reprocesso que estoura segue
matando o processo (mesmo caminho do handler novo, de propósito — supervisor
reinicia); o teto é o que impede o ciclo de ser eterno.

**Na `.dlq`, XADD antes do XACK, de propósito:** morrer entre os dois deixa a
mensagem presa e o próximo ciclo a move DE NOVO — duplicata na fila morta é
melhor que mensagem perdida. E o caminho da fila morta não assume payload
legível (`json` ilegível ⇒ `event_id=desconhecido` no log ERROR): o motivo de a
mensagem estourar pode ser exatamente um JSON quebrado.

**Como testar mensagem presa SEM esperar 60s de relógio:** `XCLAIM` aceita
`IDLE` (backdata o tempo parado), `RETRYCOUNT` (grava a contagem de entregas) e
`JUSTID` (não incrementa a contagem ao reivindicar) — juntos permitem esculpir
qualquer estado de PEL em milissegundos. Ver `_prender()` no teste. Sem isso, o
teste do limiar dormiria 60s ou o limiar viraria parâmetro injetável (e o guarda
deixaria de provar o valor real).

**`make ci` local desta célula agora precisa de `REDIS_STREAMS_URL`:** os
testes-guarda falam com Redis REAL (PEL não existe em mock). Local:
`docker run -d --name alunos-redis -p 16381:6379 redis:7` e
`export REDIS_STREAMS_URL=redis://localhost:16381/0`. Sem a variável o teste
falha com instrução no texto (fail-closed, não skip); no CI o service de
`ci-celula.yml` já fornece. Os testes usam stream com sufixo `uuid4` e limpam no
teardown — não colidem com outra sessão no mesmo Redis.

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

## Fuso: a linha é preventiva aqui; quem morde é o guarda

**Contexto:** esta célula não tem `TEMPLATES` configurado nem um `.html` sequer —
`GET /alunos/{email}/matriculas` devolve JSON e nada renderiza data para um humano.
Ainda assim `config/settings.py` fixa `TIME_ZONE = "America/Sao_Paulo"` (25/08/2026):
sem a linha valia o default de fábrica do Django, `America/Chicago`, e a falha só
apareceria na primeira tela — foi exatamente o roteiro que pegou a `sugestoes` em
24/08 (EVO-21). A classe está catalogada em `armadilhas/099`.

**O que isso obriga quem for renderizar a primeira data aqui:** nada de novo no
settings, mas `enrolled_at` (e qualquer `timestamptz`) chega do banco em UTC — a
conversão para Brasília acontece no `template_localtime` do template ou num
`timezone.localtime()` explícito, nunca no `.isoformat()` cru de um dict de resposta.
A API interna continua devolvendo ISO-8601 em UTC de propósito: fuso é assunto de
exibição, não de contrato.

**Como o guarda foi desenhado (sem tela para testar):** `tests/test_fuso_horario.py`
não confere a string do settings — isso seria tautologia e passaria com qualquer fuso
errado que alguém escrevesse ali. Ele confere comportamento, com um instante escolhido
para cair em **dias diferentes** nos dois fusos (`2026-08-25 03:30 UTC` = dia 25 em São
Paulo, dia 24 em Chicago): offset de `timezone.localtime()`, dia renderizado por um
`Engine().from_string('{{ quando|date:"d/m/Y H:i" }}')`, e o offset igual em janeiro e
agosto (o Brasil não tem horário de verão desde 2019 — um fuso com DST reprova mesmo
acertando um mês). O `Engine()` avulso existe porque a célula não tem `TEMPLATES`: dá
para exercitar a conversão do template sem inventar tela nem mexer no settings.

## A fila de liberação: por que ela é a própria `Matricula`, e o que isso obriga

**Onde:** `apps/matriculas/models.py` (status `aguardando`/`recusada` + campos da
fila), `apps/matriculas/services.py` (`matriculas_que_valem`, `entrar_na_fila`,
`decidir_na_fila`), `apps/core/api.py` (as três portas `/pre-matriculas`).
**Lei:** `docs/decisoes/DECISAO-fila-de-liberacao.md` (27/08/2026).

**A armadilha que a decisão criou, e que se fechou no mesmo PR.** Até este PR,
`GET /alunos/{email}/matriculas` fazia `Matricula.objects.filter(email=email)` —
**sem filtro de status** — e a Caixa de Sugestões faz `bool(...)` de qualquer
linha devolvida. Com três status que significavam todos "comprou", devolver tudo
estava certo; o defeito nasceria junto com `aguardando`. Uma linha na fila daria
acesso à Caixa **na hora**, que é o oposto exato do que a fila quer. Guarda:
`tests/test_fila_de_liberacao.py::test_matricula_aguardando_nao_abre_a_caixa` —
com a consulta antiga ele acusa `assert 200 == 404`.

**Lista de PERMISSÃO, não de exclusão.** O despacho pedia "excluir `aguardando` e
`recusada`". A consulta faz o contrário: `status__in=STATUS_QUE_VALEM`. A
diferença só aparece no futuro — com exclusão, todo status inventado depois nasce
**dando** acesso; com permissão, nasce sem, e alguém precisa decidir. O mecanismo
que obriga a decisão é `test_status_novo_nasce_sem_acesso`: os dois baldes
precisam cobrir exatamente `STATUS_CHOICES`, então um sexto status reprova a
suíte até ser classificado.

**`STATUS_*` são globais do módulo, com apelidos na classe.** O corpo de
`class Meta` não enxerga os atributos da classe que o contém (escopo de classe
não é herdado por classe aninhada), e a `UniqueConstraint` precisa da tupla na
`condition`. Sem as globais, a condição repetiria as strings — duas fontes para
o mesmo fato, exatamente o que a constraint existe para evitar.

**`pre:<uuid>` marca a proveniência para sempre.** Quem entra na fila não pagou,
então não há pedido. O prefixo sobrevive à liberação (a linha vira `ativa` e
continua `pre:`), e é por ele que `POST /pre-matriculas/{id}/decisao` sabe que
está decidindo sobre a fila: uma matrícula **paga** responde 404 ali, de
propósito — aquela porta não é caminho para mexer no status de quem comprou. A
guarda de que pedido real não pode começar com `pre:` mora em `matricular()`,
que é a única porta por onde entra `order_id` de fora (evento + reprocesso).

**O que a guarda do prefixo NÃO alcança:** ela protege a borda, não a tabela. Um
`Matricula.objects.create(order_id="pre:...")` escrito dentro da célula passa —
não há como expressar "esta linha nasceu na fila" como constraint de linha, já
que após a liberação um `pre:` legítimo é `ativa`. Se algum dia isso importar, o
caminho é um campo `origem` explícito, não uma constraint mais esperta.

**Idempotência com mecanismo:** `UniqueConstraint(site_id, email)` parcial (só
nos status da fila). O "já existe?" do serviço sozinho é atravessável por duas
requisições simultâneas da mesma pessoa; a constraint é quem decide, e o
`except IntegrityError` (sob savepoint — `armadilhas/027`) atualiza a linha do
vencedor. Parcial porque a mesma pessoa PODE ter várias matrículas pagas no
mesmo site — um curso cada.

**O 409 da fila usa a MESMA consulta do acesso.** `entrar_na_fila` recusa quem
já tem matrícula que vale chamando `matriculas_que_valem()`, não uma regra
paralela. Se as duas divergissem, existiria gente recusada na fila por "você já
tem acesso" que a Caixa não deixa entrar — o pior desfecho possível.

**O e-mail é normalizado (`strip().lower()`) ao entrar na fila.** A Caixa
pergunta por `email.strip().lower()`; uma linha gravada com maiúsculas seria
liberada pelo mantenedor e continuaria invisível para ela.
**Consequência sabida, fora do escopo deste PR:** o caminho de **pagamento** não
normaliza — `matricular()` grava o e-mail como o evento mandou. Uma matrícula
paga com maiúsculas já hoje é invisível para a Caixa. É bug pré-existente e vale
um despacho próprio (backfill + normalização nas duas pontas).

**`criada_em` da fila é o `enrolled_at` que já existia.** Um segundo carimbo de
"quando esta linha nasceu" seriam dois lugares para o mesmo fato. Os opcionais
(`turma`, `motivo_recusa`) moram como `""` no banco (convenção do Django para
CharField) e viram `null` na borda, que é o que o contrato declara.

**`status` fora do enum cai no padrão, em vez de erro ou lista vazia.** A direção
importa: esconder a fila faria o painel dizer "ninguém esperando" para um
mantenedor que tem gente esperando há uma semana. Mostrar demais para quem já
está autenticado no admin não custa nada; mostrar de menos custa a pessoa que
desistiu de esperar.

## O `openapi_extra` das portas novas foi GERADO do contrato, não digitado

Três operações com descrições longas em bloco (`|` do YAML) não sobrevivem a
transcrição à mão: um espaço ou uma quebra de linha a menos e o freeze acusa
divergência num texto que o olho lê como igual. O caminho que funcionou foi um
script de uso único que lê `contracts/alunos.openapi.yaml` e imprime os dicts
como literais Python — colados no arquivo e versionados como código estático.
O freeze continua sendo prova independente: ele compara o documento **exportado
pelo django-ninja** com o congelado, e o exportador não lê o contrato.

**Não use `pprint` para isso:** ele quebra string longa em pedaços concatenados
(`"OPCIONAL " "— " "pista " ...`) e o resultado é ilegível. Um serializador de
seis linhas que emite `repr()` por nó e nunca parte string resolve.

## O teste do lock oscila quando a suíte roda em SQLite (28/08/2026)

`test_inv_p5_matricula_lock.py::test_dois_consumers_mesmo_evento_em_threads_geram_uma_matricula`
falha de forma **intermitente** — `OperationalError: database table is locked:
matriculas_matricula` — quando a suíte é rodada localmente com
`DATABASE_URL=sqlite:///...`. Medido: 2 falhas em 3 rodadas do par
`test_smoke.py + test_inv_p5_matricula_lock.py`, **sem mudança nenhuma no
código**.

**Não é defeito do teste nem do código que ele protege.** Ele exercita
`select_for_update` com duas threads reais, e o SQLite implementa isso como
trava de tabela inteira, com corrida contra o timeout de lock. O Postgres — que
é o que o `ci-celula` fornece e o que roda em produção — implementa lock de
linha, e lá ele é determinístico.

**Por que isto merece estar escrito:** a primeira medição que eu fiz foi UMA
rodada, e ela dizia que os testes novos daquele PR estavam "envenenando" o
teste do lock. Passei a bisseccionar um culpado que não existia. Uma rodada só
não distingue causa de coincidência num teste com concorrência — **repita três
vezes antes de acusar a sua mudança**, e repita também o cenário de controle
(um teste antigo qualquer + o do lock).

**Regra prática:** se este teste ficar vermelho na sua máquina, rode-o isolado
e repita. O veredito dele é com Postgres, no CI. Rodada local com SQLite serve
para o resto da suíte.

## Sabotagem que não foi aplicada parece guarda sem dentes (28/08/2026)

Ao provar por mutação o filtro de escola da lista de alunos, a primeira
sabotagem "passou": 24 verdes, e por um instante pareceu que o guarda não
mordia. **A mutação nunca tinha sido aplicada** — o `sed` com `\n` no padrão não
casa (o `sed` trabalha linha a linha), e o `str.replace` que veio depois não
tinha `assert`. Aplicada de verdade, ela derruba **6** testes.

**A regra: toda sabotagem afirma que foi aplicada antes de rodar o teste.** Um
`assert` sobre o texto do arquivo, ou um `git diff --stat` não vazio — qualquer
coisa que falhe alto se a edição não pegou. Sem isso, "o guarda não mordeu" e "a
sabotagem não aconteceu" são indistinguíveis, e os dois se parecem com um verde.

É irmã da lição acima (uma rodada só não distingue causa de coincidência): as
duas dizem que **o resultado de uma medição não vale sem a prova de que a
medição mediu o que você acha que ela mediu.**



## A identidade do fato não é a do envelope (20/09/2026)



**Onde:** `PONTE_DO_V1`, `dados_na_forma_do_v2()` e `identidade_do_fato()` em

`apps/eventos/management/commands/consume_eventos.py`; `EventoProcessado.

identidade_logica`; guardas em `tests/test_o_mesmo_pagamento_nas_duas_versoes.py`.



**O buraco:** `pagamento.aprovado.v1` e `pagamento.aprovado.v2` descrevem o

MESMO fato com campos diferentes, e o v1 não sai do ar enquanto houver

consumidor nele (RITOS.md §3). As duas versões chegam com `event_id` diferente,

então o dedup por `event_id` vê dois eventos, roda o efeito duas vezes e não

reclama de nada. É a falha mais cara desta célula e a mais silenciosa.



**A regra vem do contrato, em forma de dado.** O campo `x-ponte-do-v1` do

schema v2 publica `chave_entre_versoes` (os campos de `data` que identificam o

fato) e `no_v1` (de onde tirar cada um num evento v1). `PONTE_DO_V1` é uma

CÓPIA desse dado, e `test_a_ponte_e_copia_fiel_do_contrato` reprova quando as

duas divergem. Nada aqui é interpretação nossa.



**E ela NÃO é a mesma para os avisos da família, o que é o erro fácil de

cometer:** no `pagamento.aprovado` o fato é o par (`provider`,

`provider_reference_id`), porque o `mp_payment_id` do v1 é o mesmo valor com

`provider` implícito igual a `mercadopago`. No `pagamento.recusado` o v1 NUNCA

carregou referência de provedor nenhuma, e quem atravessa as versões é o

`payment_id`. Copiar a chave de um para o outro deduplicaria recusas de

pagamentos distintos como se fossem uma. Por isso a ponte é uma tabela por

evento, e `test_todo_evento_consumido_declara_a_ponte` barra quem acrescentar

handler sem declarar a dele.



**Duas unicidades no mesmo `create`, e elas medem coisas diferentes:**

`event_id` barra a MESMA mensagem de novo (entrega at-least-once);

`identidade_logica` barra o MESMO FATO vindo pela outra versão. Tirar qualquer

uma deixa um buraco que a outra não cobre, e sob concorrência a unicidade no

banco é a única coisa que sobra: duas entregas simultâneas passam juntas pelo

`SELECT`, e quem perde o `INSERT` volta sem rodar o efeito.



**A tradução mora na BORDA, nunca no handler.** `dados_na_forma_do_v2()`

converte o v1 para a forma do v2 antes de qualquer coisa, e `ao_pagamento_

aprovado()` lê só nomes do v2 (`platform_site_id`). Um handler que decidisse a

versão pela presença de um campo estaria adivinhando o que o envelope diz por

escrito. Quando o v1 morrer, some a função e nada mais muda.



**Versão fora de `VERSOES_ACEITAS` estoura.** Tratar um v3 como se fosse v2

leria campos que podem ter mudado de nome e derivaria identidade errada:

matrícula duplicada sem uma linha de log. A recusa sobe, a mensagem fica no PEL

e a fila morta a recolhe depois de `MAX_ENTREGAS`.



**O que a migração não conseguiu trazer.** As linhas de `EventoProcessado`

anteriores a 20/09/2026 guardam só o `event_id`, e a identidade lógica daqueles

fatos não existe em lugar nenhum. Elas foram preenchidas com o próprio

`event_id`. Consequência aceita: um pagamento processado como v1 ANTES da

migração, chegando como v2 DEPOIS, passa pelo dedup de evento. Quem segura esse

caso é a idempotência de `matricular()` por `order_id`, a segunda tranca da

célula.



**Prova de mutação, e uma pegadinha nova:** seis sabotagens, seis vermelhos.

A que falhou primeiro foi tirar `unique=True` do MODELO: a suíte seguiu verde

porque o banco de teste nasce das MIGRAÇÕES, e o índice continuava lá. Sabotar

constraint de banco é sabotar a migração, não o `models.py`. É a lição

"sabotagem que não foi aplicada parece guarda sem dentes" com roupa nova.

## A identidade do fato nasce escopada pelo site (20/09/2026)

**Onde:** `identidade_do_fato()` em
`apps/eventos/management/commands/consume_eventos.py`; guardas
`test_mesma_referencia_em_escolas_diferentes_sao_fatos_diferentes` e
`test_o_aviso_do_site_errado_nao_consome_a_identidade_do_certo`.

**O buraco, achado pela frente do checkout e conferido aqui.** A chave que o
contrato publica em `x-ponte-do-v1` identifica o fato DENTRO de um tenant, e
sozinha ela não basta. O `provider_reference_id` é o id da cobrança na conta do
fornecedor, e cada escola tem a sua: duas escolas podem receber a referência
`12345` no mesmo dia, de compras que nada têm a ver uma com a outra. Sem o site
na identidade, a segunda é lida como reentrega da primeira e descartada. A
pessoa pagou, o dinheiro entrou, e a matrícula nunca acontece, sem erro em
lugar nenhum.

**Pelo outro lado é a mesma falha:** um aviso que chegue com o site trocado
grava a identidade do fato verdadeiro, e o aviso legítimo que chegar depois é
descartado como duplicado.

**A forma da chave é `platform_site_id|evento|campos da chave do contrato`**, a
mesma das outras células consumidoras deste lote, para que um fato seja legível
do mesmo jeito em qualquer uma.

**Nenhuma migração acompanhou a correção, e isto foi medido, não suposto:** a
coluna e a restrição não mudaram (o `unique` continua no mesmo campo), só o
formato do valor gravado. `manage.py makemigrations --check --dry-run` responde
"No changes detected". A migração `0002`, que cria o campo, nasceu neste mesmo
PR e nunca rodou fora de banco de teste, então não existe dado no formato
antigo em lugar nenhum para migrar.

**Prova vermelho para verde:** com a sabotagem `identidade sem o escopo do
site`, três guardas caem, dois deles dizendo a frase que descreve o dano
("a compra da segunda escola foi descartada como duplicada da primeira" e "o
aviso do site errado consumiu a identidade do fato certo"). Desfeita a
sabotagem, 16 verdes no arquivo.
