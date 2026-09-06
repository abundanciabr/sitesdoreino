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

## Sem despachante não nasce linha de `enviada` — a decisão que o degrau 4 teve de tomar

O degrau 4 (`motor.py`) entrega *"uma pessoa entra numa jornada e o passo é
AGENDADO"*. O envio de verdade é o degrau 5 (o sininho, pelo
`notificacao.devida.v1`) e o degrau 8 (o e-mail, que ainda nem sabe perguntar o
endereço à `identidade`, porque a linha `consome:` entra no PR daquele degrau).

Então existe, aqui, o momento em que a régua LIBERA um passo e **nada tem para
onde entregá-lo**. E o vocabulário de `Entrega.resultado` é fechado: `enviada`,
`pulada`, `barrada_pela_regua`, `barrada_por_preferencia`. Gravar `enviada` para
um passo que ninguém entregou seria falso-verde escrito no banco, e ele
contaminaria até o teto diário, que conta justamente as linhas `enviada`.

**A saída foi injetar o despacho.** `varrer(despachar=...)` recebe quem sabe
entregar; o padrão é `sem_despacho_ainda`, que devolve `False` e diz no nome o
que falta. Quando ele devolve `False`: nenhuma `Entrega` nasce, a inscrição NÃO
avança (o passo continua devendo e a passada seguinte o reencontra), e a
`Passada` conta isso em `sem_despacho`, para que a ausência seja um número
visível em vez de um silêncio.

**O que isso obriga na TAR-076 (degrau 5):** passar o despachante de verdade, que
publica o `notificacao.devida.v1` e devolve `True` só quando publicou. Nada mais
no motor precisa mudar — e essa é a prova de que a costura está no lugar certo.

## O cronograma é ancorado, e a linha que faz isso é uma só

`avancar()` calcula `proximo_em = inscricao.ancora_em + seguinte.atraso`. Nunca
`agora + atraso`. É essa linha que responde à pergunta do §5: se o passo 2 era
para D+2 e a régua o empurrou para D+3, o passo 3 sai em **D+5**, e não em D+6.

Trocá-la por `timezone.now() + atraso` parece inofensivo e passa em qualquer
teste de caminho feliz (onde a régua não atrasa nada). O guarda é
`test_o_passo_3_sai_em_D5_mesmo_com_o_passo_2_atrasado_pela_regua`, e ele foi
medido contra a sabotagem.

## A idempotência da inscrição tem TRÊS camadas, e a de cima não é redundante

1. **`origem_event_id`** — o mesmo FATO nunca inscreve duas vezes, nem depois de
   o episódio anterior terminar.
2. **A trava parcial do banco** (`uniq_inscricao_andando_por_jornada`) — pega a
   corrida entre dois consumidores no mesmo instante.
3. **O dedup por `event_id`** do `apps/eventos`, que é a camada de fora.

**A primeira existe porque a segunda não cobre o caso dela**, e isso é fácil de
ler como duplicação: a trava parcial só impede duas inscrições ANDANDO, então um
evento reentregue meses depois abriria um episódio novo, **legítimo pela trava e
errado pelo fato**. E a distinção não pode virar "a trava é total": trava total é
justamente o defeito que a consultoria achou, que fazia a jornada "sumiu" rodar
uma vez na vida do aluno.

A contraprova mora ao lado, em `test_um_fato_NOVO_abre_um_episodio_novo`: sem
ela, um `inscrever` que simplesmente se recusasse a inscrever de novo ficaria
verde — o defeito da trava total, disfarçado de idempotência.

## Slug de condição desconhecido PULA o passo; nunca o manda assim mesmo

`condicoes.avaliar()` levanta `CondicaoDesconhecida` para slug fora do
dicionário, e o motor trata isso como "pula, com o motivo escrito". A alternativa
tentadora (`CONDICOES.get(slug)` devolvendo `None` e o motor seguindo em frente)
transforma um erro de digitação numa mensagem enviada para quem não devia
recebê-la — e erro de digitação em slug é exatamente o tipo de coisa que passa
por revisão.

## O `LOTE` limita a PASSADA, e a `Passada` precisa saber qual lote usou

`Passada.esgotou_o_lote` comparava com a constante `LOTE` do módulo em vez do
lote que aquela passada recebeu — então toda passada reduzida (`varrer(lote=2)`)
respondia "não enchi" mesmo tendo enchido. Corrigido guardando o `lote` no
próprio relatório.

E a lembrança que o §6.3 pede: o `LOTE` limita o TRABALHO de uma passada, não o
volume do dia. Dez mil pessoas elegíveis continuam sendo dez mil envios ao longo
das passadas; quem protege a cota do provedor é a régua de capacidade, que é
outra peça (TAR-079). Ler o `LOTE` como proteção de volume é o conforto falso que
faz ninguém construir a régua que falta.

## A outbox mora em `apps/jornadas`, e não em `apps/eventos` — é fronteira, não gosto

Um leitor procura a outbox da célula em `apps/eventos`, porque é o app que já
fala de eventos. Ela não está lá, e a razão é o **critério de morte §10.7** do
plano: `apps/jornadas` pode tocar `apps/eventos` num ponto só, criando a linha de
`EnvioRegistrado`. Uma outbox lá seria uma segunda tabela alheia sendo escrita
daqui, e o critério de morte teria sido cumprido por descuido, sem ninguém
decidir nada.

Quem publica é o motor, então a outbox é do motor. E `apps/eventos` continua
sendo o que sempre foi: quem CONSOME evento e quem ENTREGA fora do site.

## Dois `tasks.py` na mesma célula é o esperado, e o que não pode é nome repetido

A célula agora tem `apps/eventos/tasks.py` (a task de envio) e
`apps/jornadas/tasks.py` (o relay da outbox). O autodiscover do djhuey varre app
por app, então os dois são registrados normalmente. **O que não se pode é os dois
registrarem uma task com o MESMO nome** — a segunda substituiria a primeira em
silêncio, e o sintoma seria um envio que nunca acontece sem erro nenhum
(`armadilhas/030` é a vizinha: worker de pé com o registro vazio).

## O despacho e o registro da entrega vivem na MESMA transação

`motor.varrer()` embrulha o par (despachar, `regua.registrar`) num
`transaction.atomic()`. Não é preciosismo, e são duas razões que se somam:

1. **Sem isso, a carta chega ao sininho e a linha de `Entrega` pode não ser
   gravada.** A passada seguinte reencontra o passo devendo e manda de novo, com
   um `event_id` NOVO — que a dedup do sininho não tem como pegar. Duas cartas
   iguais na caixa da mesma pessoa.
2. **É essa transação que satisfaz o `emitir()` da outbox**, que RECUSA gravar
   fora de transação. Uma exigência resolveu a outra.

Guarda: `test_se_a_entrega_nao_puder_ser_gravada_a_carta_tambem_nao_sai`, que
derruba o `regua.registrar` e mede que a carta sumiu junto.

## Sem `origem_event_id`, a carta não sai — e isso é fail-closed declarado

`origem_event_id` é obrigatório no contrato (`format: uuid`) e é o que torna
verdadeira a promessa *"a entrega do aviso é RASTREÁVEL"*: de qualquer aviso na
tela se chega ao acontecimento que o causou.

Uma inscrição sem origem conhecida (semeada à mão, por exemplo) **não** gera
carta. A alternativa tentadora era inventar um valor — o id da inscrição, que
também é UUID e caberia no formato. Isso deixaria uma pista que não leva a lugar
nenhum, e uma pista falsa é pior que a ausência dela. Toda jornada deste desenho
é disparada por evento (§5), então a origem sempre existe no caminho real.

## O `assunto` da carta de sequência é `jornada.passo`, e isso não se decide aqui

Rito de Contrato de 31/08/2026, com o mantenedor presente (§8.7.1). Boas-vindas é
INCENTIVO, então a carta leva `jornada_slug` + `passo_id` e **o texto não viaja**
— o sino o busca na hora de ler. Inventar um assunto próprio para boas-vindas
exigiria um Rito de Contrato novo, e não é decisão de quem constrói.

O guarda que impede a invenção: `test_a_carta_tem_exatamente_os_campos_que_o_contrato_exige`,
que lê o contrato NO DISCO e confere os dois lados (campo a mais reprova tanto
quanto campo a menos, porque o contrato é `additionalProperties: false`).

## Todo handler passa a receber o `event_id`, e isso fechou uma limitação antiga

O `LICOES.md` desta célula registrava, desde a receita R4, que *"o handler recebe
só `envelope["data"]` — sem `event_id`"*. Era limitação conhecida e conviveu bem
enquanto a idempotência de negócio bastava.

O que forçou a mudança: a carta de um passo de sequência exige `origem_event_id`
no contrato, e é ele que torna verdadeira a promessa *"a entrega do aviso é
RASTREÁVEL"*. Sem o `event_id` chegando ao handler, a inscrição nasceria sem
origem e o despachante, que é fail-closed, **nunca publicaria carta nenhuma** —
a sequência inteira ficaria muda sem um erro sequer.

Hoje `processar_envelope` chama `handler(envelope["data"], envelope["event_id"])`.
O parâmetro tem default nos três handlers de pagamento, que não o usam: os testes
que os chamam com um argumento só continuam valendo.

## O `gatilho` da jornada é o nome no FIO, sem a versão

`identidade.pessoa-cadastrada`, e **não** `identidade.pessoa-cadastrada.v1` — que
é como o plano cita o contrato. A versão viaja no envelope; o nome do stream e o
nome do evento não a carregam.

Errar isto é a falha silenciosa mais fácil deste degrau inteiro: o consumidor
recebe, o handler roda, o filtro por `gatilho` não acha jornada nenhuma, e
ninguém é inscrito. **Nada erra, nada reclama, e a sequência simplesmente não
acontece.** Guarda que amarra as duas pontas uma na outra:
`test_o_gatilho_da_jornada_casa_com_o_stream_que_a_celula_escuta`.

## Semear é CONTEÚDO, não esquema: comando de gerência + workflow, nunca migração

O caminho curto seria uma migração de dados. Ele já foi tentado no fórum e a
suíte respondeu com 20 testes quebrados — migração de dados entra no banco de
TODO teste. Por isso a semeadura é `manage.py semear_boas_vindas`, e quem a roda
na produção é `.github/workflows/semear-boas-vindas.yml`, o mesmo desenho de
`semear-economia` e `semear-areas-do-forum`.

**E o site sai de dentro do contêiner, nunca de um valor escolhido à mão.** A
jornada é achada por `site_id`, e semear com o site errado criaria uma jornada
que nenhum cadastro encontra: tudo responde 200, a linha existe no banco, e
ninguém nunca recebe nada. O script lê `SITE_ID` do contêiner da `gamificacao` (a
única célula que o declara) e, **se a `identidade` já publicou algum cadastro,
COMPARA com o site que aquele evento carimbou de verdade** — divergiu, para. É
medir em vez de supor, no ponto exato em que supor não daria erro nenhum.

## A varredura periódica é a peça cuja ausência não dá erro

`tasks.varrer_jornadas`, de cinco em cinco minutos, é o que faz o motor ANDAR. Sem
ela, tudo o que a escada construiu fica parado: as inscrições existem, os passos
têm hora marcada, e ninguém nunca passa para olhar. Nenhum teste de unidade
acusaria, porque cada peça funciona.

Cinco minutos, e não um: o relógio das sequências é de DIAS, a janela fecha às
20h e o teto é diário. Um passo que espera cinco minutos não muda nada para o
aluno, e cada passada tem custo.

O import de `despacho` e `motor` é DENTRO da função: `despacho` importa `tasks`
(precisa do `relay_apos_commit`), então importá-los no topo fecharia um ciclo.

## A fila de proxima acao nao e uma segunda `condicoes.py`, e a diferenca cabe numa pergunta

**O risco real:** o degrau 15 do `PLANO-PAINEL-DE-GESTAO.md` pede "regra por
dimensao" e esta celula ja tem um dicionario de regras (`condicoes.py`). Quem
ler os dois rapido conclui que sao a mesma coisa e constroi um duplicado, que e
a doenca que esta casa mais combate.

**A pergunta que separa os dois, e ela e curta:**

- `condicoes.py`: *"este PASSO, de uma jornada em que a pessoa JA ENTROU, ainda
  faz sentido no instante do envio?"* Automacao ja escolhida, resposta binaria.
- `proxima_acao.py`: *"olhando a pessoa inteira, qual e o proximo gesto e QUEM
  o faz?"* Nada foi escolhido ainda, e a resposta pode ser justamente **nao
  automatizar** (a professora fala, ou um robo investiga).

Por isso o roteador nao reimplementa nada: ele le `EstadoDoAluno` (a mesma
projecao) e chama a regua, e decide um andar acima. Se um dia a resposta for a
mesma nos dois arquivos, o defeito e no de cima.

## O teto de contato saiu da regua e virou parametro com dono

`regua.TETO_POR_DIA = 1` era numero solto: a lei estava citada no comentario e o
DONO da decisao, em lugar nenhum. Ele agora mora em `parametros.py`, com dono,
unidade e motivo, e a regua **le de la** em vez de guardar uma copia (dois
lugares para o mesmo numero e o mesmo defeito por outro nome).

**A fronteira que evita o proximo engano:** nem todo numero vira parametro.
`DIAS_DE_SILENCIO_ATE_CHAMAR_GENTE` fica DENTRO da regra, em `proxima_acao.py`,
porque muda-lo muda a regra, e regra que muda tem de subir de versao. Um limiar
morando em `parametros.py` mudaria sem passar pela versao, e a promessa "regra
versionada" do §6.4 do plano viraria prosa.

## "Regra versionada" so e verdade com impressao digital, e a assinatura inclui o CODIGO

Um campo `versao: int` que ninguem e obrigado a mexer e a categoria "garantia sem
mecanismo" da `RETROSPECTIVA-FASE-D.md`. O que faz a promessa valer e
`impressao_digital()`: um sha256 sobre slug, versao, executor, as duas frases **e
o `inspect.getsource` da condicao**, com o par (versao, assinatura) fixado a mao
em `tests/test_proxima_acao.py`.

**O corpo da condicao entra de proposito.** Uma regra pode mudar inteira sem que
uma letra das frases mude, e e exatamente essa a mudanca que passa despercebida
numa revisao apressada. O preco assumido: reformatar o arquivo (um `black` que
quebre a linha da condicao de outro jeito) tambem derruba o guarda. Isso e
barulho aceito, porque o silencio do outro lado seria uma regra trocada sem
ninguem notar.

## O guarda de venda foi provado contra uma regra que NAO existe no codigo

Nao ha regra de venda em `REGRAS`, e nao pode haver hoje (diretiva do mantenedor
de 22/08/2026, §9 do plano). Ainda assim o guarda "sucesso do aluno antes de
venda" existe e e testado: a regra de venda vive DENTRO do teste, escrita de
proposito para casar com qualquer pessoa.

**A razao vale para qualquer guarda desta casa:** guarda testado so contra codigo
correto nao guarda nada. Este funciona no dia em que alguem escrever a regra
errada, que e o unico dia em que ele importa. E ele foi provado dos DOIS lados
por mutacao: trocar a condicao por `if regra.e_de_venda:` (recusar venda sempre)
tambem derruba um teste, porque um guarda que barra tudo desligaria a fila em
silencio e passaria como se estivesse certo.

## O sinal de sucesso e "entregou um checkpoint", nao "abriu uma aula"

`teve_resultado_na_escola()` le `EnvioDeCheckpoint`, e a escolha foi deliberada:
quem abriu a aula e nao entregou nada nao colheu nada, e vender para essa pessoa
e exatamente o que o guarda existe para impedir. O sinal ainda nao sabe se o
trabalho foi APROVADO (o laudo e fato da celula `cursos` e nao chega aqui), e
apertar o sinal um dia so pode REDUZIR o que a fila oferece de venda: e o lado
seguro da duvida.
