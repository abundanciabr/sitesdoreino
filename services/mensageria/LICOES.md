# LICOES.md — mensageria

Decisões e armadilhas específicas desta célula. Formato: `Decisão/Sintoma →
Causa/Razão → Solução`. O que vale para qualquer célula vai no `ARMADILHAS.md`
da raiz, não aqui.

## O handler do R4 recebe só `envelope["data"]` — sem `event_id`

**Contexto:** a receita R4 (`CAMINHO-DOURADO.md`) chama `handler(envelope["data"])`
dentro de `consume_eventos.py` — o `event_id` fica só no envelope, nunca chega ao
handler. A idempotência por `event_id` (INV desta célula: "reentrega ⇒ 1 envio")
acontece **inteiramente** na camada de fora, via `EventoProcessado.objects.create()`
(unique em `event_id`) — se isso falhar com `IntegrityError`, o handler nem roda.
**Decisão:** o handler usa uma SEGUNDA chave de idempotência, de negócio
(`order_id` + `tipo` + `canal`, unique em `EnvioRegistrado`), como defesa em
profundidade — cobre também o caso de uma task do Huey ser reexecutada e cair de
novo no handler. As duas camadas são independentes e a segunda não substitui a
primeira: se algum dia o `event_id` deixar de estar disponível fora do handler,
ainda assim não duplica envio.
**Origem:** Despacho mensageria/envios (R4+R8).

## Falha de provedor precisa estourar, não ser engolida

**Sintoma que teria acontecido:** se `processar_envio()` capturasse a exceção do
provedor e não relançasse, o `@huey.task(retries=5, retry_delay=30)` nunca saberia
que precisa reagendar — a task terminaria "com sucesso" tendo, na prática, falhado
silenciosamente.
**Solução:** `processar_envio()` registra a tentativa/erro no `EnvioRegistrado` e
depois **relança** (`raise`) — é a exceção escapando da função que o decorator do
Huey usa como sinal de retry. Ver `test_provedor_fora_do_ar_...` em
`tests/test_retry_provedor.py`, que prova isso (a exceção `ConnectionError`
precisa aparecer em `pytest.raises`, não ser engolida).
**Origem:** Despacho mensageria/envios (R8).

## Cobertura de teste do `consume_eventos.py` (o loop do Redis Stream em si)

**Corrigido em parte, e a parte que faltava escondia um bug.** O texto original
dizia que o arquivo "segue a receita R4 ao pé da letra e não tem teste automatizado
próprio", e que a garantia estava coberta pelas duas camadas abaixo. As duas camadas
existem e continuam válidas — mas **nenhuma delas alcançava a lógica de dedup dentro
do `handle()`**, e era exatamente lá que morava o descarte silencioso (ver a última
lição deste arquivo). Hoje `processar_envelope()` vive fora do `handle()` e é testada
direto, sem Redis: `test_inv_mensageria_evento_atomico.py`. O que continua sem teste é
só o loop `xreadgroup`/`xack` em si.

A garantia de "reentrega ⇒ 1 envio" está coberta em duas camadas testáveis sem Redis:

1. `EventoProcessado` — unicidade de `event_id` testada direto no modelo
   (`test_event_id_repetido_estoura_integridade`).
2. Os handlers — chamados 2x manualmente, testando o `get_or_create` por
   `order_id+tipo+canal` (`test_handler_chamado_duas_vezes_gera_um_unico_envio`).

Se uma sessão futura quiser um teste de integração do loop inteiro, `fakeredis`
(ou um Redis real via `docker compose -f docker-compose.dev.yml up -d redis`) é o
caminho — não existe ainda.

## Extensão pendente: template por site (`TEMPLATES_POR_SITE`)

`apps/eventos/handlers.py` já tem o ponto de extensão (`TEMPLATES_POR_SITE`, hoje
vazio) para customizar assunto/corpo por `site_id`, com fallback automático para o
template padrão da plataforma — satisfaz o invariante multissítio estruturalmente,
mas nenhum site pediu override ainda. Quando pedir, é só popular o dict (ou trocar
por uma tabela, se a lista crescer) — a função `_resolver_template()` já resolve
o fallback.

## Eventos ainda não consumidos: `pedido.criado.v1` e `quiz.completado.v1`

`constituicoes/AGENTS.mensageria.md` lista esses dois eventos na seção "Escuta",
mas o despacho desta sessão (mensageria/envios) pediu explicitamente só os três
do fluxo de pagamento: `pagamento.aprovado`, `pix.expirado`, `pagamento.recusado`.
Ficam de fora por escopo, não por esquecimento — próximo despacho.

## Dedup de evento e efeito do evento vivem na MESMA transação

**Onde:** `apps/eventos/management/commands/consume_eventos.py::processar_envelope()`.

**O bug (esteve em `main` até o PR desta lição):** o `create()` do `EventoProcessado`
rodava solto dentro do `handle()` — sem savepoint algum — e **commitava** antes de o
handler rodar. Se o handler falhasse por motivo transitório (SMTP fora, deadlock,
conexão caída), o evento já estava marcado como processado.

**Aqui isso era pior do que em `alunos` e `leads`, e a diferença importa:** o caminho de
dedup desta célula chama `r.xack(...)` antes do `continue`. Ou seja, a reentrega
descartada era **removida do stream** — não ficava na PEL, não sobrava nada para
recuperar depois. Nas outras duas células a mensagem ao menos sobreviveria a uma
recuperação futura via `xautoclaim`; aqui, não.

E há uma janela de falha parcial concreta: `ao_pagamento_aprovado()` chama
`_registrar_e_enfileirar()` **duas vezes** — e-mail e depois WhatsApp, cada um na sua
própria transação. Bastava a segunda falhar para o WhatsApp nunca mais ser enviado, com
o e-mail já entregue e o evento marcado como visto.

Demonstração crua contra o código anterior:

```
--- depois da falha ---
EventoProcessado gravado? True
--- depois da reentrega ---
processar_envelope devolveu: False -> handle() faz r.xack() e descarta
Envios registrados: 0
Chamadas ao provedor: 0
```

**A estrutura correta são duas transações aninhadas** — a externa envolvendo registro e
efeito, a interna sendo savepoint só em volta do `create()`. O detalhe que fecha o
raciocínio: **com o fix, o `xack` do dedup volta a ser seguro.** `False` agora só
acontece quando o efeito daquele evento realmente commitou alguma vez; antes, `False`
também significava "marcado mas nunca feito", e era nesse caso que o ack destruía a
mensagem.

**A armadilha da correção óbvia:** mover o handler para dentro do `try` faria um
`IntegrityError` vindo dele ser lido como "já processado". Não é hipótese — a constraint
`uniq_envio_por_order_tipo_canal` é disputada por `get_or_create()` sob corrida. O
guarda desse caso colide na constraint real.

**Por que a reentrega não duplica envio:** esta célula já tem a segunda camada de
idempotência por chave de negócio (`EnvioRegistrado`, por `order_id+tipo+canal`). A
transação externa entra sem risco de duplicata — a camada de negócio absorve o retry.
É por isso que "refazer o evento inteiro" é seguro aqui.

**Consequência no loop do Redis (sabida, não corrigida aqui):** com a exceção propagando
para fora de `processar_envelope()`, o `xack` não roda e a mensagem fica na PEL. É o
comportamento desejado, mas a recuperação de mensagens presas (`xautoclaim`) não existia
nesta célula — dependia de o processo reiniciar. **Resolvido nesta célula pelo despacho
reentrega-pel (lote 2) — ver a lição "Reentrega do PEL + fila morta" abaixo.**

**Origem:** varredura das quatro células que consomem eventos, depois dos mesmos
consertos em `alunos` (PR #43) e `leads` (PR #46). Três das quatro tinham o mesmo bug,
todas herdado da receita R4 — `checkout` escapou por não usar a tabela de dedup.

## Entrypoint oficial do worker: `python manage.py run_huey` (fecha o lado-célula do H10.2)

**Contexto:** até este despacho o worker de produção subia por um bootstrap de 6
linhas embutido no `command:` do compose (ARMADILHAS §4.11), porque `manage.py
run_huey` não existia. Agora existe: `huey.contrib.djhuey` está em INSTALLED_APPS
e o comando faz o `django.setup()` + `autodiscover_modules("tasks")` sozinho.

**As duas regras que mantêm isso funcionando:**
1. **`settings.HUEY` DEVE ser a MESMA instância de `config/huey.py`** (o settings
   importa `from config.huey import huey as HUEY`). O djhuey aceita uma instância
   pronta; se alguém trocar por um dict de config, nasce uma SEGUNDA fila — o
   handler enfileira numa, o worker escuta a outra, e nenhum e-mail sai, sem erro
   nenhum. Teste-guarda: `tests/test_entrypoint_huey.py` (os 3 testes reprovavam
   contra o código anterior — vermelho→verde real).
2. **`config/huey.py` não pode ser fail-hard no import.** Com djhuey instalado, o
   `settings.py` importa esse módulo — ou seja, o container WEB também passa por
   ali no boot. Por isso `HUEY_REDIS_URL` é lido com `os.environ.get(...)` e
   default inofensivo (o pool do redis-py é preguiçoso, nada conecta no import);
   produção define o valor real em `infra/env/mensageria.env`, compartilhado
   pelos três containers da célula. Trade-off assumido: o worker não morre mais
   no boot se a var faltar — ele apontaria para localhost e ficaria surdo; a
   guarda contra isso é o env de produção ser um arquivo só para web+worker
   (faltou para um, faltou para todos, e o web denuncia).

**Prova viva (22/08/2026, local, Redis efêmero):** `run_huey` logou
`+ apps.eventos.tasks.enviar_notificacao` sob `The following commands are
available:` (o sinal do §4.11), e uma task enfileirada pelo caminho real foi
executada — `EnvioRegistrado` saiu de `pendente` para `enviado`/`resultado=ok`.

**O que NÃO mudou aqui:** o `command:` do `mensageria-huey` no compose ainda é o
bootstrap antigo — a troca para `python manage.py run_huey` é escopo do despacho
de infra do mesmo lote. O bootstrap antigo continua funcionando com este código.

**Origem:** despacho mensageria/entrypoint-huey (H10.2).

## Reentrega do PEL + fila morta: o delivery_count é lido DEPOIS do claim, e o claim soma 1

**Contexto:** o consumer agora reivindica mensagens presas (`XAUTOCLAIM`,
`min_idle_time=IDLE_MS_REENTREGA`) a cada iteração, ANTES do `xreadgroup ">"`, e
reprocessa pelo MESMO caminho das novas (`_processar_e_ack`). Quem já esgotou
`MAX_ENTREGAS` vai para `<stream>.dlq` com o payload original + `motivo`,
`delivery_count`, `movida_em`, é ACKada e loga ERROR com o `event_id`. Desenho e
constantes são convenção do lote 2 — as 4 células consumidoras têm o MESMO;
não "melhore" só aqui.

**A pegadinha do off-by-one:** a regra é "delivery_count do PEL já em
`MAX_ENTREGAS` ⇒ fila morta", mas o próprio `XAUTOCLAIM` **incrementa** o
contador ao reivindicar. Como o código lê o PEL (`xpending_range` do msg_id)
DEPOIS do claim, `_entregas_ja_feitas()` subtrai 1 para recuperar o valor que a
regra compara. Remover esse `- 1` daria uma entrega a menos a cada mensagem —
e nenhum teste de caminho feliz veria.

**Para plantar delivery_count arbitrário em teste, sem loop:** `XCLAIM` com
`retrycount=N` **grava** o contador direto (não incrementa) — é assim que
`tests/test_reentrega_pel.py` cria uma mensagem "na 5ª entrega" numa chamada só.

**Redis dos testes vem de `REDIS_STREAMS_URL`, nunca de porta fixa:** local é o
container exclusivo do lote (16383); no CI o service `redis:7` responde em 6379
— a env já aponta certo nos dois. Sem a env, o teste **falha** com mensagem
clara (fail, não skip: pular seria verde falso, §5.6).

**O que a fila morta NÃO tem ainda:** consumidor. O log ERROR é o único alarme;
reprocessar uma mensagem do `.dlq` é operação manual (`XRANGE` + `XADD` de volta
no stream original). Se o volume aparecer, um comando de reprocesso é despacho
pequeno.

**Origem:** despacho mensageria/reentrega-pel (lote 2), fechando a linha
"evento que faz o handler estourar fica pendente para sempre" do ARMADILHAS §9.

## O `order_id` sintético das jornadas cabe em 100 — e é por isso que as chaves são UUID

**Contexto:** o motor das sequências (`apps/jornadas`) reusa de propósito a trava
do fluxo de dinheiro, `uniq_envio_por_order_tipo_canal`, escrevendo `order_id`
sintético `jornada:<inscricao_id>:<passo_id>` (§4.1 do
`PLANO-SEQUENCIAS-DE-MENSAGENS.md`). `EnvioRegistrado.order_id` é
`CharField(max_length=100)`, e essa coluna **não se toca**.

**A conta, e por que ela decidiu o tipo da chave primária:** `jornada:` são 8
caracteres, dois UUIDs são 72, os dois `:` são 2 — **81**, com 19 de folga. Com
chave primária inteira caberia igual; com qualquer coisa mais larga que UUID, não.
Então a escolha de `Inscricao.id` e `Passo.id` serem `UUIDField` tem duas razões
que se somam, e é bom que as duas estejam escritas: o `passo_id` **sai da célula**
(é o id opaco do ramo `jornada.passo` do contrato, e id sequencial atravessando
fronteira conta quantos passos a escola tem para quem só devia ver o próprio
aviso), e o `order_id` sintético precisa caber sem migração no fluxo de pagamento.

**A guarda:** `tests/test_jornadas_travas.py::test_o_segundo_episodio_nao_some_em_silencio_pela_trava_do_pagamento`
mede `len(order_id) <= EnvioRegistrado.order_id.max_length` contra o campo real,
nunca contra o número 100 escrito à mão. Se alguém encolher a coluna, o teste cai.

## Versão publicada é PEDRA, e isso precisou de gatilho — a chave estrangeira não bastava

**A promessa:** o mantenedor troca a frase de uma sequência quando quiser, e
ninguém que já está no meio dela vê a frase mudar embaixo de si (§5).

**O que parecia bastar:** `Inscricao` apontar para `JornadaVersao` em vez de para
`Jornada`. Isso garante que ninguém TROQUE de versão no meio do caminho — e é a
correção 1.2 da consultoria. Mas não garante nada sobre o CONTEÚDO daquela
versão: um `UPDATE` no `TextoDoPasso` de uma versão publicada muda o texto de
quem já está andando, e a tela do degrau 7 existe justamente para o mantenedor
reescrever frases. Era "garantia sem mecanismo" um andar abaixo da correção.

**O mecanismo:** três gatilhos `BEFORE UPDATE OR DELETE`, na migração `0001` de
`jornadas`, em `jornadas_jornadaversao`, `jornadas_passo` e
`jornadas_textodopasso`. Rascunho (`publicada_em` NULL) continua livre — é onde a
tela mexe. **Publicar é o último `UPDATE` que a linha aceita.**

**O que isto obriga em quem for construir a tela (TAR-078):** editar uma
sequência publicada é **criar a versão seguinte e copiar os passos**, nunca
alterar os que existem. Não é preferência de estilo: o banco recusa a alternativa.

**Prova vermelho→verde, medida:** com as três linhas de `GATILHO_*` removidas da
migração, `test_publicar_e_o_ultimo_update_que_a_versao_aceita` e
`test_o_texto_de_uma_versao_publicada_nao_muda_embaixo_de_quem_esta_nela` falham
com `DID NOT RAISE`.

## `django.contrib.postgres` entrou em INSTALLED_APPS, e não é dependência nova

`Passo.canais` é `ArrayField` — lista de canais, porque sino entregue + e-mail
devolvido + WhatsApp barrado são três resultados independentes. É o `ArrayField`
que torna a restrição `canais <@ ARRAY['sino','email','whatsapp']` expressável
como `CheckConstraint` (`Q(canais__contained_by=...)`), no banco e não em Python.

A entrada em `INSTALLED_APPS` é a instalação documentada do Django para os campos
de `contrib.postgres`. Não cria tabela, não tem migração própria, e não amarra a
célula a nada novo: ela já é Postgres em produção, em dev e no CI.

## O que `Passo.janela` significa, porque o plano não disse

O §5 lista o campo `janela` no `Passo` e não o define. Só existe uma leitura
compatível com o resto do plano, e ela está escrita no `models.py`: **por quanto
tempo o passo continua fazendo sentido depois de ficar elegível** (nulo = não
expira). A leitura tentadora — "a janela de horário desta jornada" — é o critério
de morte §10.4 (*"a régua do §6 ganhar exceção 'só para esta jornada'"*): a janela
de silêncio (nunca antes das 8h, nunca depois das 20h) é UMA SÓ e vale para toda
entrega da célula.

Fica registrado aqui para a TAR-072 e a TAR-073 não terem de adivinhar, e para
que uma leitura diferente seja uma decisão declarada em vez de um acidente.

## `array_length` engana no SQL cru, não no ORM — e a diferença foi medida

A restrição "passo sai por algum canal" é `~Q(canais=[])`. A explicação natural
para essa escolha — *"`canais__len__gt=0` deixaria o vazio passar, porque
`array_length` de array vazio é NULL"* — **foi medida e é falsa pelo ORM**: o
Django gera `coalesce(array_length("canais", 1), 0) > 0`, e o `coalesce` fecha o
buraco. As duas grafias funcionam.

**A armadilha existe, e é do SQL escrito à mão.** Conferido em psql:
`CHECK (array_length(c, 1) > 0)` **aceita** o array vazio — `array_length` de
vazio é NULL, `NULL > 0` é NULL, e `CHECK` que devolve NULL passa; a linha entrou.
Esta célula tem `RunSQL` de verdade na migração das jornadas, então a distinção
vale ser lembrada aqui.

Fica registrado também pelo motivo do §"não afirmar diagnóstico sem medir": a
explicação errada quase entrou num comentário de código com voz de fato, e quem a
desmentiu foi a sabotagem deliberada, não a releitura.

## O teto diário conta só a `Entrega`, e isso é fronteira, não esquecimento

A régua conta quantas mensagens já saíram para a pessoa no dia consultando
`Entrega` — tudo que sai pelo motor das jornadas. Ela **não** conta o envio
transacional antigo da célula (`EnvioRegistrado`, do `apps/eventos`), e não pode:
ler aquela tabela é o **critério de morte §10.7** do plano, que permite a este
app apenas CRIAR a linha de `EnvioRegistrado`.

**A consequência, dita por inteiro:** um e-mail de pagamento aprovado que sair às
14h não consome a vaga do dia, e uma mensagem de jornada às 18h ainda passa. Isso
é uma frouxidão conhecida, e ela é o preço da fronteira que o mantenedor escolheu
ao pôr o motor dentro desta célula (§8.2). Se um dia esse duplo incomodar, o
conserto NÃO é ler a tabela vizinha: é o motor passar a registrar `Entrega`
também para o caminho transacional, ou a separação em célula voltar à mesa com a
medição na mão, como o próprio §10 manda.

**O que a régua conta, e por quê:** toda classe, inclusive as que passam por fora
dela. A régua protege a ATENÇÃO de uma pessoa, e atenção não distingue classe —
uma mensagem de serviço recebida às 10h é uma mensagem recebida. O que a classe
decide é que ela nunca é BARRADA, não que ela seja invisível.

## Às 20:00 em ponto a janela já fechou, e a fronteira é declarada

"Nunca depois das 20h" tem uma leitura em que 20:00 cravado ainda passa. Fica
FECHADA (`ABRE <= hora < FECHA`): às 20:00 a mensagem já lê como "de noite" para
quem recebe, e na dúvida a régua cala. Está escrito num teste com nome próprio
(`test_as_20h_em_ponto_a_janela_ja_fechou`) para que uma leitura diferente seja
uma decisão de alguém, e não um acidente de `<` contra `<=`.

## Ausência de preferência NÃO é recusa, e o fail-closed é sobre outra coisa

As duas coisas moram a três linhas de distância no mesmo arquivo, e confundi-las
desligaria a plataforma para todo mundo no primeiro dia:

- **Ausência** (nenhuma linha de `Preferencia`): a pessoa nunca disse nada, e
  quem nunca disse nada não silenciou nada. Vale aceitar.
- **Ilegível** (o banco fora, a linha corrompida, a consulta estourando): a régua
  não conseguiu se pronunciar. Vale NÃO enviar, com o motivo gravado na
  `Entrega` — silêncio por dúvida, nunca mensagem por dúvida.

O §6.2 diz "preferência ilegível", e a palavra é essa de propósito.

## O desempate mora na régua, não na varredura

`ORDEM_DE_DESEMPATE` e `em_ordem_de_desempate()` ficam em `regua.py` porque a
ordem É regra da régua: quando duas jornadas disputam a vaga do dia, ganha a
inscrição mais antiga. Quem varre (TAR-073) só precisa obedecer, e obedecer
significa CHAMAR essa função, nunca reescrever um `order_by` equivalente. Duas
implementações da mesma ordem divergem no primeiro dia em que alguém mexer numa
delas, e a divergência aqui é invisível: os dois códigos continuam ordenando,
só que diferente.

O segundo critério (`inscricao__id`) não é enfeite: dois `criada_em` iguais
(mesmo lote, mesmo instante) empatariam de novo, e um empate que sobra é um teste
que passa hoje e falha amanhã sem nada ter mudado.

## `registrar` é `update_or_create`, e um `create` estouraria na segunda passada

A trava do §5 é `unique(inscricao, passo, canal)`: uma linha por entrega, por
canal. Um passo barrado pela régua **reagenda**, então a varredura seguinte
reavalia a MESMA entrega — e é essa linha que passa de `barrada_pela_regua` para
`enviada` quando a vaga abre. Com `create`, a segunda passada bateria na trava.
