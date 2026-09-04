# CONFRONTO | o quinto documento ("Growth Execution Engine v1.0") contra as decisões da casa

**Escrito em 04/09/2026**, pela mesma lei que produziu o
`CONFRONTO-scale-os.md` um dia antes: `armadilhas/299` proíbe derivar plano de
documento externo sem confrontar cada premissa com `docs/decisoes/`, com a
memória e com o código em `origin/main`. Primeiro os vereditos, depois o plano.

O documento é o **quinto** da mesma IA externa, e o primeiro escrito como
**playbook de implementação para agentes de IA**: 100 seções, dos princípios
(§1 a §5) às entidades (§6 a §33), às telas (§34, §35), à semana operacional
(§36 a §41), aos agentes (§42 a §51), à qualidade de dado (§52 a §55), à
infraestrutura (§56 a §61), às oito fases (§62 a §70), aos critérios de
sucesso (§71 a §82), aos cinco marcos (§83 a §87) e ao fecho (§88 a §100).
Guardado inteiro em `SCALE-OS-5-growth-execution-engine.md`.

---

## §1 A conclusão, antes da tabela

**Das 100 seções, 91 repetem premissas que o confronto de 03/09 já julgou, e
nenhum veredito muda.** O documento é a mesma tese em roupa de manual de
execução: onde os quatro anteriores diziam "o que medir", este diz "em que
ordem construir". Isso o aproxima ainda mais da casa, e por isso a tabela de
"já existe com outro nome" ficou ainda maior que a de ontem.

Sobram **oito peças novas**, e uma delas é a melhor ideia dos cinco
documentos: **o grafo causal** (§1, §27, §97, §100). Ela é também a única
peça grande que a casa realmente não tem, e isso foi MEDIDO nesta sessão,
não suposto (§4.1).

E há **uma armadilha grande**, que é o motivo de este confronto existir antes
de qualquer PR: seguido ao pé da letra, este documento manda criar a célula
`scale_os` (§4), as rotas `/scale-os/` (§35), o banco de tarefas (§27) e o
`ADR` (§63). Uma sessão sem contexto faria isso em um lote, e teria duplicado
a célula `metricas` (que nasceu e fechou em 04/09), o `/admin/` (que é a porta
da gestão) e a `fila/` (que é o motor de tarefas desde 29/08). Seria a lei
anti-duplicação violada em três lugares no mesmo dia.

---

## §2 O mapa: as 100 seções contra os vereditos que já existem

Cada linha aponta para o veredito do `CONFRONTO-scale-os.md`, que continua
valendo. Nada aqui é decisão nova.

| Seções deste documento | O que pedem | Já julgado em | Veredito que continua |
|---|---|---|---|
| §4, §35, §56, §57, §95 | Célula `scale_os`, rotas `/scale-os/…`, aba nova, `/api/scale-os/v1/`, `docs/scale-os/` | itens 6 e 7 | **MANTIDA.** Uma célula (`metricas`, no ar desde 04/09), telas em `/admin/<coisa>/`, porta de leitura `/api/metricas/`, plano em `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`. |
| §5, §58, §94 | Banco como fonte da verdade, para evitar conflito entre agentes | item 8 | **MANTIDA, e ver §4.8:** a dor é real e foi medida aqui; a cura da casa não foi banco. |
| §26, §27, §28, §29, §45, §77 | Motor de tarefas, Kanban de 8 colunas, `execution_contract`, `lease`, orquestrador, Definition of Ready | item 8 | **JÁ EXISTE.** `fila/` + `ci/fila.py` + `ci/reservar.py` (trava atômica no servidor, expira em 3 h) + `celulas.yml`/`toca` + `RUNBOOK-LOTES.md` + `/admin/caixa/robos/`. |
| §6, §7, §8, §9, §10, §11, §12, §41 | StrategicCycle, Objective, KeyResult, WIG, Lead/Lag Measure, placar, trajetória semanal | item 19 | **JÁ EXISTE com outro nome:** o ciclo é `DECISAO-o-calendario-do-ciclo.md` (no ar 04/09, meta repartida por curva semanal); a MCI é a Meta 1 (`compras-no-ciclo`); as medidas de direção são `pedidos-de-entrada-por-semana` e `liberacoes-em-48h`; o placar é `/admin/placar/`. Ver §4.2 para a única lacuna. |
| §13, §15, §16, §53 | Status configurável, `MetricDefinition`, `MetricSnapshot`, dimensões, qualidade por métrica | itens 10 e 30 | **JÁ EXISTE.** `painel/cartoes/` (21 cartões) com `direcao`, `unidade`, `frescor_maximo`, `dimensoes`, `limiar_ambar`, `limiar_vermelho`, `autoridade`, `versao`; a foto é a célula `metricas`. |
| §14 | Funil AARRR com camada de conversão | itens 5 e 23 | **MANTIDA.** Aquisição, VSL, checkout e receita dependem de venda e de anúncio, congelados desde 22/08. Entram desenhados (`sem_fonte_porque`), nunca acesos. |
| §17, §18, §19 | `GrowthBottleneck`, motor de gargalos, `confidence` e `evidence_level` | item 22 | **JÁ EXISTE, e foi construído:** cartão `restricao-da-semana` e `services/admin/apps/core/restricao.py` (degrau 1, no ar 03/09). Suspeita é cálculo; confirmada é registro dele. |
| §20, §21, §22, §23, §71 | Hipótese, experimento, aprendizado, biblioteca, ICE/RICE | itens 24 e 25 | **JÁ DESENHADO** (degrau 12 do plano). A biblioteca de aprendizado é `armadilhas/` (303 entradas, com sino que avisa quando a assinatura reaparece). |
| §24, §25, §36, §37, §38, §39, §40 | Sprint, uma restrição por sprint, segunda-feira, sexta-feira, retrospectiva, `Commitment` | itens 19 e 21 | **JÁ EXISTE, e foi construído:** `/admin/reuniao/` com os oito passos (degrau 3); o compromisso é registro tipo `compromisso` com prazo, e o veredito cumprido/não cumprido é calculado do livro (degrau 2). |
| §31, §32, §33, §50, §51 | `AgentRun`, `AuditEvent`, `Decision`, revisão/exceção, evidência antes de "pronto" | itens 9, 11, 12 | **JÁ EXISTE.** Auditoria append-only com trigger no banco; registro tipo `decisao` com `responde_a` e `vence_em_dias`; `pendencia` com os quatro campos; `evidencia` + `verificado_em` como condição de verde. |
| §30, §59 | Idempotência, eventos internos | item 13 | **JÁ EXISTE.** `contracts/eventos/*.json` com `additionalProperties: false`, consumo idempotente por `event_id` como lei, 36 contratos de evento congelados. |
| §34, §88, §89, §90 | Tela que prioriza decisão, Command Center, UX para o dono, compressão gerencial | item 26 | **JÁ É LEI.** As oito réguas de toda tela (`PLANO-PAINEL-DE-GESTAO.md` §2), o teto de nove blocos da capa com teste-guarda, `feedback_painel_leigo`. |
| §42, §43, §44, §46, §47, §48, §73 | Seis agentes de IA com nome, copiloto, red team, contrato de saída | item 32 | **MANTIDA a ordem (por último).** Nasce UM robô analista (degrau 16), não seis. Ver §4.6 sobre o revisor. |
| §49, §60, §61, §68 | Aprovação humana, menor privilégio, feature flag, autonomia | itens 12 e 15 | **MANTIDA.** `ADMIN_EMAILS` é a porta; robô não tem crachá de sessão; interruptor por porcentagem de público não tem sujeito (um leitor). |
| §52, §54, §55, §69 | Entrada manual, CSV, APIs, detector de anomalia | itens 30 e 31 | **JÁ DESENHADO** (degrau 11). Medição digitada com autoridade `mantenedor` já é o padrão da casa. Ver §4.5 sobre a severidade do alerta. |
| §62, §63, §64, §65, §66, §67, §70, §92, §93 | As oito fases e os dez lotes (descoberta, ADR, domínio, contrato, UI, laço semanal, inteligência) | §3 inteiro | **JÁ FEITO ou já ordenado.** Ver §3: a descoberta, o ADR, o modelo de domínio e o contrato de API da célula de medição foram executados entre 03 e 04/09. |
| §72, §82 | Previsão, cenários, "não fazer no MVP" | item 31 | **MANTIDA.** Nada de previsão antes de doze meses de coorte (`PLANO` §9). O documento concorda consigo mesmo aqui. |
| §76, §78, §79, §80, §91 | Dez regras dos agentes, Definition of Done, qualidade, testes mínimos, prompt-mãe | (novo em forma, velho em conteúdo) | **JÁ EXISTE** como `CONSTITUICAO.md`, `RITOS.md`, `INVARIANTES.md`, o orçamento de 15 arquivos, a prova vermelho a verde e o despacho da fila. As dez regras do §76 são um resumo fiel da constituição desta casa, escrito por quem nunca a leu. |
| §98, §99, §100 | Três cérebros, o loop, a estrela arquitetural | (fecho) | **É a tese.** Ver §4.1: o grafo causal é o que falta para o fecho ser verdadeiro aqui. |

---

## §3 O que mudou na casa entre os quatro documentos e este

O documento não pode saber, e quem for lê-lo precisa saber:

Entre 03/09 à noite e 04/09, a escada do plano andou de 0 a 7. Estão **no ar e
conferidos**: o placar com a barra do mês e a meta do ciclo (degrau 0), a
restrição da semana (1), a direção da semana (2), o modo reunião (3), o placar
de doze e as duas estrelas-guia (4), as três latências (5), o bloco "o que
mudou desde a semana passada" (6) e **a célula `metricas` inteira** (7): evento
imutável com trava dupla, fila de eventos mortos, recepção por Redis Streams,
porta de leitura `/api/metricas/` com guarda de 401, contrato congelado em
`contracts/metricas.openapi.yaml`, e a `admin` já lendo dela.

A consequência para este documento é direta: **o LOTE A (descoberta), o LOTE B
(contratos), o LOTE C (foundation) e boa parte do LOTE E já foram executados**,
com outros nomes e para a célula certa. As fases §62 (reconhecimento), §63
(ADR), §64 (modelo de domínio) e §65 (contrato de API congelado) não são
trabalho a fazer: são trabalho feito, e o §62 do próprio documento manda não
assumir arquitetura pelo playbook quando o repositório pode mostrar a
realidade.

---

## §4 O que é novo de verdade

### 4.1 O grafo causal (§1, §27, §97, §100) | **NOVA, e é a melhor peça**

O documento exige que toda tarefa responda "que resultado estratégico esta
tarefa move?" e que todo indicador responda "que ações estão sendo executadas
para movimentá-lo?". O §97 transforma isso em teste: pegue qualquer cartão do
Kanban e caminhe até o Objetivo, e depois volte.

**Medido nesta sessão, em `origin/main`, não suposto:**

- Uma tarefa da fila tem `id`, `titulo`, `toca`, `depende_de`, `cria`,
  `evidencia_exigida`, `despacho`, `origem`, `criada_em`. **Nenhum campo
  aponta para um número do placar.** E o validador é fail-closed: campo
  desconhecido reprova (`ci/fila.py`, `CAMPOS_DA_TAREFA`), então o elo não
  pode nascer por convenção; precisa de PR.
- O caminho de volta existe só como **prosa**. O campo `acao` do cartão
  `compras-no-mes` diz: *"a fila de entrada é onde se age"*. É uma frase, não
  um elo: a tela não sabe listar as tarefas que trabalham naquele número.
- São **123 tarefas** na fila hoje. **46 tocam só a fábrica** (`ci`, `infra`,
  `painel`, `contracts`, `.github`, as leis) e **77 tocam alguma célula do
  negócio**. Esse é um proxy pelo campo `toca`, e é o mais longe que se
  consegue chegar sem o elo: `toca` diz em que pasta a tarefa mexe, e **nunca**
  diz que número ela pretende mover. É exatamente o buraco que o §1 aponta.

Veredito: **NOVA**, entra no plano, e é barata: um campo opcional na tarefa
(que número esta tarefa move) e a regra de cálculo inversa no painel (que
tarefas estão trabalhando neste número). Não precisa de célula, de banco, nem
de venda.

### 4.2 A camada OKR acima da meta (§2 camada 2, §6, §7, §8) | **JÁ EXISTE, com uma lacuna pequena**

`StrategicCycle` é `DECISAO-o-calendario-do-ciclo.md` (no ar 04/09);
`KeyResult` e `WildlyImportantGoal` são a mesma coisa aqui, a Meta 1; o
`Objective` é a estrela-guia. A lacuna real: o ciclo da casa não guarda os
campos `vision` e `strategic_thesis` do §6, isto é, **o ciclo sabe as datas e a
curva, e não sabe por que existe**. É uma linha no cartão, não uma entidade.

Não nascem `Objective` e `KeyResult` como camadas separadas: com uma meta e um
leitor, seriam a mesma frase escrita três vezes, e a lei anti-duplicação
proíbe. Esse é o mesmo veredito de "sem sujeito" que o confronto de ontem deu
aos onze papéis de acesso e à equipe comercial.

### 4.3 A classificação `whirlwind` (§1) | **NOVA, e barata**

Separar explicitamente "trabalho que mantém a operação de pé" de "iniciativa
de crescimento", para não confundir atividade com progresso. Hoje a casa não
consegue responder isso (a medição do 4.1 é proxy por pasta, e pasta não é
propósito). Entra junto com o elo do 4.1: é o valor que o campo assume quando
a tarefa não move número nenhum, e é honesto que a maioria das tarefas de
fábrica assuma esse valor.

### 4.4 Os níveis de autonomia 0 a 5 (§87) | **NOVA como vocabulário, JÁ EXISTE como prática**

A casa já opera em níveis: o robô analista do degrau 16 é nível 1
(recomenda); um despacho da fila é nível 3 (executa o reversível dentro de
limites); caminho CODEOWNERS exige mandato, o que é nível 2; e o nível 5 não
existe por construção, porque quem mergeia é a pista e não o agente. O que
falta é a régua escrita num lugar só. Entra no plano como parágrafo, sem
código.

### 4.5 Severidade e fadiga de alerta (§54, §55) | **PARCIAL**

As sondas e o sino existem, e o alarme da `main` abre issue. O que não existe
é o alerta como objeto com `severity`, `confidence`, `business_impact` e
`resolution_status`, nem a regra de que nem todo desvio vira alerta. Entra no
degrau 11 (a confiança), que já estava no plano.

### 4.6 O revisor que não é o autor (§47) | **JÁ EXISTE, com sujeito melhor**

O documento quer um agente revisor. A casa tem algo mais forte e mais barato:
o portão (`ci/mergear.py`), as muralhas e a pista são a segunda opinião, e são
independentes do autor **por construção**, o que um segundo agente não é
(mesmo modelo, mesmo viés, mesmo contexto). O caso do PR #1020 em 04/09
mostrou isso na prática: a espera declarou verde e foi o portão, não outro
robô, que recusou (virou TAR-141).

### 4.7 O teste do laço semanal inteiro (§81) | **NOVA como mecanismo**

Os dezesseis passos, de "ciclo ativo" a "placar atualizado", como um teste de
integração. A casa tem os pedaços testados e nenhum teste que percorra o laço
inteiro. Entra no degrau que fecha o ciclo (13), como o guarda desse degrau.

### 4.8 "A fonte da verdade deve ser banco, não Git" (§5) | **MANTIDA, e vale responder por extenso**

É a única seção que argumenta contra uma decisão da casa com um motivo
técnico, e o motivo é verdadeiro: arquivos versionados sofrem conflito quando
vários agentes escrevem ao mesmo tempo. **A casa mediu essa dor**: em 30/08
dois PRs foram devolvidos pela pista pelo mesmo conflito, e um PR de quatro
arquivos levou oito tentativas para entrar (`armadilhas/156`).

A cura não foi banco. Foi o desenho da Onda 3: **fonte multiescritor (um
arquivo por fato, ninguém edita o do outro), materialização de escritor único
(o índice e o painel são gerados, não versionados) e validação independente**.
Depois disso, dois robôs do mesmo lote deixaram de colidir sem terem escrito
uma linha em comum. Trocar isso por um banco custaria a auditabilidade (o
`git log` é a trilha), a revisão por PR e o funcionamento sem servidor, e
resolveria um problema que já não existe.

O que o documento acerta e a casa adota: "arquivos gerados devem ser
reconstruíveis deterministicamente" (§94) já é lei aqui, provada em todo PR
por `ci/muralha-do-indice.sh`.

---

## §5 O que entra no plano

Um degrau novo, e três parágrafos.

**Degrau 19, o grafo causal** (4.1 e 4.3): a tarefa passa a poder declarar que
número ela move, ou declarar-se `manutencao` (o `whirlwind` do documento, em
português). O painel ganha o caminho de volta: de um número, a lista das
tarefas que trabalham nele. O teste do §97 vira o guarda do degrau: de uma
tarefa se chega ao número, e do número se volta às tarefas.

Os três parágrafos: os níveis de autonomia (4.4) no `PLANO` §9; a severidade
do alerta (4.5) no degrau 11; o teste do laço inteiro (4.7) no degrau 13.

---

## §6 O que volta para o mantenedor

**Nada de novo.** Este é o resultado mais útil deste confronto: as cinco
perguntas do confronto de ontem (`CONFRONTO-scale-os.md` §5) foram respondidas
em 03/09 e não se repetem (`armadilhas/299`, passo 3). Este documento não
levanta nenhuma divergência nova com uma decisão dele: ele repete as mesmas
premissas de venda, checkout, equipe e CRM que já foram julgadas, e as peças
novas (§4) são todas escolhas de mecanismo, que são minhas.

A única coisa que muda de mão é a **ordem**: o plano dizia que o próximo passo
era o degrau 8 (os fatos que faltam), e o degrau 8 contém a única peça da
escada que exige ele na cadeira ("como você conheceu a escola?" é Rito de
Contrato, `PLANO` §10 item 4). O degrau 19 não exige nada dele.
