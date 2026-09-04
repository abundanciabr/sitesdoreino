# RUNBOOK DO LOTE — como reger vários despachos em paralelo

> **Para a SESSÃO-MAESTRO** — a janela raiz do Claude Code, a que conversa com o
> mantenedor. Os agentes de célula **não** leem este documento: eles recebem briefs
> fechados (§4), e carregá-lo neles seria desperdício de contexto (Alavanca 2).
>
> Nascido em 22/08/2026, no dia em que as duas trancas do throughput caíram: o
> merge passou ao agente (PR #58, Lei 4; `docs/decisoes/DECISAO-merge-pelo-agente.md`)
> e a regra serial foi aposentada (PR #59, Alavanca 1). Este runbook é o **como**
> que aquelas duas decisões destravaram.

---

## §0 — Para você, humano: como pedir um lote

Cole isto numa sessão nova (janela raiz do Claude Code, no seu PC — `PS C:\>`):

```
Leia RUNBOOK-LOTES.md e toque um lote com a fila do painel.
```

Variações que funcionam igual:

- `...com os despachos X, Y e Z` (você escolhe o conteúdo)
- `...um lote menor (3 despachos)` (gasta a franquia mais devagar)
- `...só o canário` (1 despacho, para ver a esteira rodar de ponta a ponta)

Só isso. A sessão monta, dispara, vigia, **mergeia** e te reporta no fim. As únicas
coisas que podem voltar para você são as do §7 (segredos, VPS, contrato) — e virão
como **um bloco único de colar, com a janela rotulada** (CLAUDE.md).

**Sobre custo:** um lote consome a franquia do plano mais rápido *por hora* — é o
mesmo trabalho, só que junto. Lote menor = mesmo total, ritmo mais suave.

---

## §1 — O que é um lote

**1 lote = N despachos em PARALELO + 1 janela de merge serial no fim.**

- Cada despacho em célula/área **distinta** (a cerca 1 PR = 1 célula é a proteção
  real — CONSTITUICAO Lei 2.3); cada um em worktree próprio (RITOS §1).
- Duas tarefas na MESMA célula não rodam em paralelo: viram **fila interna**
  (uma atrás da outra, no mesmo agente ou em agentes sucessivos).
- Os merges saem **serial, um a um, pelo portão** (RITOS §2 peça 4) — executados
  pela maestro, nunca pedidos ao humano.

## §2 — Montagem (antes de disparar qualquer agente)

1. **Fonte da fila:** o pedido do mantenedor > painel (`painel/painel.html`, a caixa
   "Precisa de você" — que é CALCULADA dos registros, não uma lista mantida) >
   PLANO-10X (ondas). O pedido dele é o **mandato** —
   inclusive para os caminhos CODEOWNERS que o lote tocar (Lei 4).
2. **Recorte pela cerca:** 1 PR = 1 célula. Conte os arquivos de cada despacho NO
   PAPEL antes de escrever o brief (orçamento de 15 é portão mecânico — ARMADILHAS §5.1).
3. **Brief fechado por despacho** (template em CAMINHO-DOURADO §2): célula, arquivos-
   alvo, o que é somente-leitura, evidência exigida (vermelho→verde), receitas citadas
   por número — e as **armadilhas daquela tarefa já injetadas** (§3, regra 3).
4. **Pré-voo da maestro** (5 min): `git fetch` + main verde? `alarme-main` sem issue
   `main-vermelha` aberta? plataforma saudável (último deploy verde)? `gh auth status`
   ok? Docker de pé (H4 — suba já, não no meio)?

## §3 — As sete regras de inteligência (o coração deste runbook)

1. **Ordene pelo dinheiro.** A pergunta que ordena o lote: *"o que separa a
   plataforma de alguém conseguir comprar?"* — o caminho crítico manda (Alavanca 5).
2. **Canário na frente.** O 1º merge do lote é o despacho mais simples e inofensivo.
   Se ele atravessa tudo (PR → portão → merge → deploy → saudável na VPS), a esteira
   está provada HOJE — só então as células de dinheiro entram na janela.
3. **Contexto sob medida.** Cada brief leva SÓ as receitas e armadilhas daquela
   tarefa (ex.: consumer de evento ⇒ §4.12; célula com SCRIPT_NAME ⇒ §4.10; script
   `.sh` ⇒ §3.12). Agente afogado em documentação erra mais e custa mais.
4. **Prova proporcional ao risco.** Célula de dinheiro ⇒ evidência no transporte
   (respx — §6.9) e/ou reprodução em ambiente prod-like; célula comum ⇒ suíte padrão.
   "Deveria funcionar" não é evidência em lugar nenhum (Lei 6).
5. **FAIL ≠ ERROR.** FAIL = código errado ⇒ o agente conserta. ERROR = instrumento
   quebrou ⇒ problema de ambiente, NÃO se mexe no código ([INV-CI01]). Rotear o
   vermelho certo para a resposta certa é metade da regência.
6. **Sucesso parcial é sucesso.** 5 verdes + 1 travado ⇒ mergeiam-se os 5, o travado
   é isolado com diagnóstico e reportado. O lote é colheita, não tudo-ou-nada.
7. **Contenção (anti-metas do PLANO-10X).** Sem refatoração "de passagem", sem célula
   ou rito novo, sem golpes de red-team fora dos de dinheiro. Orçamento estourou por
   coesão legítima ⇒ **pare e avise**, nunca esprema arquivos.

## §4 — Execução (a vigília)

- Dispare os agentes em paralelo, um por despacho, cada um com seu brief. Se o brief
  nomeia worktree, dispare **sem** isolamento de worktree do harness (ARMADILHAS §8.1)
  — o agente cria o dele pelo RITOS §1.
- **Regras anticolisão vão DENTRO de cada brief:** arquivo de texto compartilhado
  (ARMADILHAS, tabela do red-team, bloco `env:` do `ci-celula.yml`) ⇒ cada sessão
  escreve SÓ a própria entrada/linha e faz `git fetch origin && git rebase
  origin/main` antes do push (§7.6). Conflito só de proximidade ⇒ as duas linhas
  sobrevivem, nunca se descarta a alheia.
- **Agente parado ≠ lote parado.** A maestro segue com os demais e volta ao parado.
- **Regra de parada vale dentro do lote:** 2 correções consecutivas falharam ⇒ o
  agente faz `git reset --hard <último-verde>` e reporta (RITOS §2.2). A maestro
  decide: re-briefar com diagnóstico melhor OU tirar o despacho do lote.

## §5 — A janela de merge (serial, um a um, na ordem do §3)

Para cada PR verde, na ordem canário → comuns → dinheiro:

```bash
python ci/mergear.py <N> --conferir     # os checks acabaram? tudo verde?
python ci/mergear.py <N> --confirmo <N> # mergeia e confere state=MERGED
```

- Vermelho, pendente, ausente ou ERROR ⇒ **não mergeia**: conserta ou fica fora do
  lote. O botão do site não é caminho (Lei 4).
- **Merge que dispara deploy** (`services/**` ⇒ `deploy-celula`; `infra/**` ⇒
  `deploy-infra`): antes do PRÓXIMO merge, leia o veredito REAL do run —
  `gh run view <id> --json status,conclusion` — nunca o exit de um pipe (§5.10).
  Deploy verde ⇒ próximo merge. Deploy vermelho ⇒ **pausa a janela**: diagnostique
  (`gh run view <id> --log-failed`); causa externa (ex.: registry) ⇒
  `gh run rerun <id> --failed`; causa no código ⇒ o raio de explosão é 1 célula —
  os merges das OUTRAS células podem continuar, o da célula quebrada espera.
- Se o GitHub acusar conflito num PR depois dos merges anteriores (raro entre
  células distintas): o agente daquele PR faz rebase e o portão roda de novo.
- **CODEOWNERS no lote** (`pagamentos`, `checkout`, `contracts/`, `infra/`, `ci/`,
  `.github/`, arquivos-lei): merge só com o mandato do §2.1, e cada um **anunciado
  nominalmente** no relatório final (Lei 4).

## §6 — Fechamento (é parte do lote, não epílogo)

1. **Livro de ocorrências** (`painel/registros/`, molde em `painel/LEIA-ME.md`): um
   registro NOVO por PR, por deploy e por incidente da janela — sem perguntar antes
   (CLAUDE.md), seguido de `node painel/gerar_manifesto.js`. Registro nunca se edita:
   correção ou resposta é outro registro, com `responde_a`.
2. **Lições:** cada agente registrou as dele no próprio PR (só a própria linha);
   a maestro registra as lições **de regência** (o que o lote ensinou sobre lotes).
3. **Relatório único, em linguagem de resultado** ("os leads invisíveis agora
   aparecem"), contendo: a tabela do placar (abaixo), os anúncios de fortaleza,
   o que ficou de fora e por quê, e o que sobrou para o humano (§7) — em bloco
   único de colar quando for comando.

**Placar do lote (formato padrão do relatório):**

| Despacho | Célula | PR | Portão | Merge | Deploy | Resultado em 1 frase |
|---|---|---|---|---|---|---|
| ... | ... | #N | PASS | ✅ agente | run verde | ... |

## §7 — O que NUNCA entra num lote / o que fica com o humano

- **Rito de Contrato** (RITOS §3): sessão de arquitetura com o mantenedor presente.
  O lote pode *esperar* um contrato, nunca *mudá-lo*.
- **Segredos, VPS/SSH, console do provedor, settings do GitHub**: só do mantenedor.
- **e2e de fechamento e drill de rollback**: seriais por natureza — fecham um ciclo,
  não entram no meio de um.
- **Red-team fora dos golpes de dinheiro** (anti-meta do PLANO-10X).
- **Refatoração oportunista** de qualquer coisa que funciona.

## §8 — Modos de falha conhecidos e a resposta certa

| Sintoma | Resposta |
|---|---|
| Check vermelho num PR do lote | FAIL ⇒ agente conserta (máx. 2 tentativas); ERROR ⇒ ambiente/instrumento, não toque no código |
| Conflito em arquivo de texto compartilhado | rebase + as duas linhas sobrevivem (§7.6) |
| Deploy vermelho após merge | pausa da janela; `--log-failed`; externa ⇒ rerun; código ⇒ só aquela célula espera |
| Agente sumiu/travou | lote segue; re-brief com diagnóstico ou corte do despacho |
| Orçamento de 15 estourou por coesão | **pare e avise** — nunca fundir arquivos para caber (anti-meta) |
| Dois despachos precisam da MESMA célula | fila interna, nunca paralelo |
| Algo exige aprovação/segredo do humano | isole o passo, termine o resto, entregue UM bloco de colar rotulado |

## §9 — Lições de regência (o que cada lote ensinou sobre lotes)

**Lote da fila do painel — 03-04/09/2026** (cinco frentes montadas do quadro AO VIVO do
balcão e da caixa calculada do livro, nunca de memória: o canário do livro · a corrente
das encomendas (#949 → #953) · o resgate dos quatro PRs parados desde 31/08 · três
defeitos medidos do CI em fila interna · a tela das sequências no admin):

1. **O primeiro pouso do lote testa o INSTRUMENTO de pousar, não a esteira — e aqui ele
   reprovou o instrumento.** O canário atravessou tudo, e mesmo assim o `--e-pousar`
   morreu, nos DOIS primeiros PRs (#954 e #956), no mesmo ponto: o portão recusou com
   `ERROR` no instante exato em que o último check ficou verde, e os dois pousaram com um
   `mergear.py --pousar` repetido à mão. Não era azar. O GitHub recalcula o `mergeable`
   quando a árvore se mexe, então `UNKNOWN` é **provável justamente naquela janela** — a
   automação mirava no pior segundo possível, todas as vezes. **Duas falhas no mesmo ponto
   são medição, não coincidência:** a maestro parou de despachar, curou (#964,
   `armadilhas/308`, remede só o `ERROR` com a marca do recálculo; `FAIL` segue sem
   remedição) e o PR da cura foi pousado pela própria cura. Corolário para a montagem:
   **o canário tem de rodar pela MESMA automação que os agentes vão usar** — provar a
   esteira com um atalho à mão esconde exatamente a classe de defeito que só aparece
   quando ninguém está olhando.

2. **O repasse do achado precisa sair do lote, e não há canal para isso.** O Lote A ensinou
   a repassar aos agentes em voo; este mediu a outra metade. A ferramenta é compartilhada
   com sessões que **não são do lote**, e em menos de uma hora três sessões independentes
   escreveram três armadilhas para o mesmo defeito (`306`, `308`, `310`). O repasse aos
   três despachos meus funcionou; para as vizinhas só restou comentar no PR delas depois do
   fato. Pior: duas das três entradas ensinam um conserto manual que a cura torna **errado**,
   e um robô futuro faria a dança à toa. Corolário: `gh pr list` no início **não** é "os PRs
   do lote" — pergunte a cada agente quais são os dele, conte com vizinhas, e trate
   duplicação de catálogo como trabalho de fechamento da maestro.

3. **O quadro só mente pelo papel que ninguém escreveu — e mente nas duas direções.** A
   TAR-078 aparecia `bloqueada — esperando TAR-076` enquanto o trabalho da TAR-076 estava
   no ar desde 02/09: faltava só o evento `concluida`, que a sessão construtora nunca
   escreveu. Um arquivo destravou uma frente inteira. Do outro lado, a TAR-082 aparecia
   `na fila`, isto é, anunciada como trabalho disponível, quando já estava construída,
   mergeada e esperando apenas o mantenedor testar no próprio celular — a maestro escreveu
   o evento `bloqueada` com o motivo. **O estado é calculado e honesto; a única mentira
   possível é o evento que ninguém escreveu.** Antes de aceitar um bloqueio, meça se o
   bloqueador é código ou papel.

4. **Resgatar PR antigo começa medindo se a `main` já o superou.** Dos quatro parados desde
   31/08, um pousou e dois foram FECHADOS como superados (#734 pelos #871/#873, #761 pelos
   #907 a #911) — um deles com o ramo 894 commits atrás. A hipótese natural ("estavam
   verdes, basta atualizar") era falsa em dois de três. E o gesto que fecha o resgate é
   perguntar **o que morre junto com o PR fechado**: aqui o código havia sobrevivido duas
   vezes, porque outra sessão o refez sem ler o PR aberto (`armadilhas/287`), mas a lição em
   prosa que explicava o PORQUÊ não tinha vindo junto e teria morrido no fechamento
   (recuperada no PR de fechamento, em `services/sugestoes/LICOES.md`). Receita completa em
   `armadilhas/305`.

5. **A isenção de "só escrituração" é `painel/` e/ou `fila/`, e `armadilhas/` NÃO entra
   nela.** O #740, um PR de uma armadilha só, foi recusado com "nenhum registro viaja neste
   PR" e custou uma volta de checks. Vai para todo brief que preveja entrada de catálogo.

**Lote A da gamificação — 01/09/2026** (as quatro bordas da gamificação, uma por célula:
o backfill do Fundador · a etiqueta de nível no fórum · o quadrinho de progresso na home ·
as frases das cartas no sininho; PRs #826, #827, #828, #829 mais o #831 de fechamento —
**4 merges, 4 deploys verdes, 0 revert**, com dois passos do mantenedor devolvidos juntos):

1. **O achado do canário vale para o lote inteiro se a maestro o repassar na hora — e a
   janela para repassar é curta.** O canário mediu que o portão pode reprovar *"nenhum
   registro viaja neste PR"* por LATÊNCIA da API do GitHub, com o registro já a bordo: o
   `git ls-remote` mostrava o SHA novo e o `gh pr view --json headRefOid` ainda devolvia o
   anterior, por até dois minutos. Mandei o aviso aos três despachos em voo, com a cura
   (sondar o `head.sha`, não escrever um segundo registro). **Os três confirmaram ter batido
   no mesmo atrito depois de receber o aviso**, e nenhum escreveu registro duplicado. Sem o
   repasse, a reação óbvia — e cara — seria pagar a "dívida" de novo, criando recibo falso no
   livro. Corolário para a montagem: o canário não serve só para provar a esteira; ele é o
   primeiro sensor do lote, e o que ele mede tem de virar mensagem antes de os irmãos
   chegarem no mesmo ponto.

2. **Espera que mede a coisa errada é indistinguível de espera legítima — e só quem está de
   FORA percebe.** Um despacho armou uma sonda para esperar o GitHub enxergar o commit dele
   e ficou parado reportando "ainda não" por dois minutos. Medi de fora, dos dois lados
   (`gh pr view --json headRefOid` e `git ls-remote`): os dois já devolviam o mesmo SHA havia
   um tempo. A sonda esperava uma condição **já satisfeita** — provavelmente aninhamento de
   aspas perdido ao atravessar o script. Mandei matá-la em vez de consertá-la, e o despacho
   seguiu. **A regra: quando um despacho reporta espera repetida sem progresso, a maestro
   mede o alvo por conta própria antes de deixá-lo esperar mais.** O teto salva do infinito;
   ele não salva de esperar a coisa errada.

3. **Três dos quatro despachos acharam um teste que não testava nada — e os três acharam
   pelo mesmo gesto, depois do verde.** Mutação deliberada do código já verde. Os falsos-verdes
   eram todos da mesma família, "a asserção tem mais de uma causa suficiente": um guarda de
   regra de produto que passava porque uma `CheckConstraint` do banco já impedia o caso por
   outro motivo; um guarda de preguiça que passava porque o cliente também desistia por falta
   de env; um guarda de validação em que um campo inválido escondia o outro. **Nenhum dos três
   apareceria no CI, hoje ou nunca.** Injete "prove cada guarda por mutação DEPOIS do verde"
   em todo brief — é o único passo do rito que encontra esta classe, e ele rendeu três
   armadilhas novas (264, 265, 266) num lote de quatro.

4. **O plano que manda no lote pode citar uma cerca que já caiu, e medir isso ANTES do brief
   muda a forma dos despachos.** O `PLANO-LOTES-DA-GAMIFICACAO.md` abre dizendo que "um PR
   toca uma célula (a cerca do CI faz valer)". A cerca caiu em 29/08/2026 (Onda 5), e hoje
   `ci/cerca-de-celula.sh` só cobra o Rito de Contrato. Ler o script em vez de acreditar no
   plano permitiu que os despachos do fórum e do funil levassem **o próprio script de
   provisionamento** no mesmo PR da tela, em vez de exigirem dois PRs de infra em separado.
   É a lição 2 do Lote 10 na direção contrária: lá a opção oferecida não existia; aqui a
   restrição declarada não existia mais.

5. **Robô que escreve o registro dele marca `precisa_do_dono: false` mesmo quando cria um
   passo que só o mantenedor executa — e a caixa calculada fica cega.** Dois despachos
   entregaram scripts de provisionamento (senha de máquina, Lei 5) e os dois registraram a
   entrega como se nada esperasse por ninguém. A caixa "Precisa de você" é calculada de
   pedido sem resposta: ela não consegue esquecer, mas também não consegue adivinhar um
   pedido que ninguém escreveu. **Fechamento de lote passa a incluir uma conferência
   explícita:** todo despacho que produziu passo humano tem registro com `precisa_do_dono:
   true`, e se não tiver, a maestro escreve o que falta. Aqui virou o registro `20260901-027`.

6. **O scratchpad é COMPARTILHADO entre as sessões de um lote.** Um despacho escreveu o corpo
   do PR num arquivo com nome genérico e outro o sobrescreveu no meio do trabalho. Não custou
   nada desta vez (o corpo já vivia no GitHub), e podia ter custado. **Vai para o brief:
   arquivo temporário de despacho leva o nome da célula no nome.**


**Lote 10 — 25-26/08/2026** (o lote que a resposta do mantenedor reescreveu no meio: a lei
das notificações + a Fase 1 dela + o canário da constituição + o falso-verde do `contrato-check`
em 9 PRs; PRs #201, #210, #202–#209, #211, #212 — **12 merges, 9 deploys verdes, 0 revert**, com
dois reruns por blip de SSH e uma renumeração de armadilha causada por sessão vizinha):

1. **A decisão do mantenedor pode chegar com o lote JÁ EM VOO — e a lei ainda assim entra
   primeiro.** As três respostas sobre o sininho chegaram depois de os agentes estarem
   despachados. A regra do Lote 9 (decisão vira lei ANTES do despacho que a implementa) não se
   cumpre esperando o lote seguinte: **abre-se uma frente NOVA de lei dentro do lote corrente e
   ela vai para a frente da janela de merge** — aqui, o PR #201 foi o primeiro merge, antes de
   qualquer implementação. Corolário: a Fase 1 do plano já estava despachada e continuou válida
   porque o brief dela não dependia das respostas; brief que não pressupõe a decisão pendente é
   o que permite despachar antes dela.

2. **Item de fila que oferece duas opções pode ter só uma — meça a muralha antes do brief.** O
   H12 dizia, havia semanas, "decidir se a correção entra de uma vez (8 arquivos) ou por
   célula". Quinze minutos lendo `ci/cerca-de-celula.sh` mostraram que a cerca conta
   `services/<x>/` no diff e reprova acima de 1 célula **sem válvula nenhuma** — a label
   `arquitetural` relaxa o ORÇAMENTO (>15 arquivos), jamais a cerca. "De uma vez" nunca existiu.
   O despacho nasceu **9 PRs em ordem obrigatória** e as 8 células saíram na primeira tentativa.
   Escrever o brief pela opção inexistente teria custado um agente descobrindo isso no vermelho.

3. **O instrumento da própria maestro caiu na lição 25 — e a defesa teve de virar código.**
   Escrevi um script de janela serial que tratava todo exit≠0 do `mergear.py` como "pare". No
   segundo merge veio `ERROR: mergeable=UNKNOWN` — o GitHub recalculando, que é "não consegui
   medir", nunca "reprovado" — e a janela parou por rotina. **Saber a armadilha não protege;
   executar o passo protege**, e quando o passo é automático, a distinção FAIL×ERROR tem de
   estar DENTRO do automatismo: o script agora remede até 6 vezes em ERROR e só então pausa.
   Todo automatismo de janela precisa distinguir as duas coisas do mesmo jeito que o portão.

4. **Guarda que nasce vermelho de propósito é a melhor prova de fora que existe — se a ordem de
   merge for respeitada.** O #211 (o guarda do `contrato-check`) foi aberto reprovando com
   `6 célula(s) com contrato-check fora da lei` e **ficou verde sozinho** quando a oitava célula
   mergeou. Nada além da realidade mudou de cor: o próprio pipeline contou o defeito encolher de
   6 para 0. Quando um lote conserta N lugares iguais, **peça o guarda no mesmo lote e mergeie-o
   por último** — ele deixa de ser promessa e passa a ser medição.

5. **A tabela §1 do humano mentiu por horas, e foi encontrada assim por quem montava lote PELA
   tabela.** O H21 (o passo do mantenedor para a área administrativa) continuava 🟡 "aguardando
   você" muito depois de ele ter rodado a linha e a área estar no ar — medido de fora nesta
   sessão: `/admin/healthz` 200, `/admin/` 302 para o login. É a lição 10 do Lote 9 acontecendo
   no documento que existe justamente para não mentir. **A linha do §1 se fecha na MESMA resposta
   em que o passo humano é confirmado, com a evidência de fora colada** — nunca "depois".

6. **O pré-voo do lote seguinte é a última rede do lote anterior.** O último `deploy-celula` da
   `main` estava VERMELHO desde a noite anterior (`dial tcp :22: i/o timeout`, o runner sem
   alcançar a VPS) e ninguém tinha lido o veredito. Um rerun bastou. O mesmo blip voltou no
   oitavo merge deste lote — e a resposta certa continuou sendo **medir antes de diagnosticar**
   (três sites em 200 e a porta 22 devolvendo o banner SSH do PC), e só então repetir. Dois
   episódios em 24h ainda são blip; três em uma semana viram estrutura, e aí vale reabrir o
   §3.17.

7. **Documentação de partida que diverge do CI custa o baseline de TODO despacho — e o agente
   certo é quem topa com ela.** O `ARMADILHAS.md` §2 mandava subir só o Postgres e exportar 3
   variáveis; o `ci-celula.yml` declara postgres **e** redis e **7** variáveis. O agente das 8
   células bateu em `Redis real inacessível` logo no primeiro baseline — e a leitura literal do
   rito ("baseline não verde ⇒ pare e reporte") mandaria abortar oito despachos por instrumento
   ausente na máquina, que é ERROR e não FAIL. Ele **registrou em vez de contornar**
   (`armadilhas/119`); a maestro corrigiu a fonte no mesmo lote, e o §2 agora traz a lista
   completa e diz, com todas as letras, que "pare e reporte" existe para `main` quebrada e não
   para container que você ainda não subiu.

8. **Sessão vizinha rouba número de armadilha mesmo com a maestro numerando.** Atribuí 117 a um
   despacho (a correção do Lote 8, lição 3). Enquanto o lote rodava, **outra sessão mergeou o PR
   #213 e levou o 117**. O rebase acusou conflito só em `armadilhas/INDICE.md`, e a resolução foi
   a de sempre: renomear o arquivo para o primeiro número acima de todos (120, pulando o 118 e o
   119 já reivindicados), regenerar com `python ci/indice_de_armadilhas.py` e **caçar as citações
   internas** — havia uma no `LICOES.md` da célula, que o rebase não veria. A atribuição da
   maestro reduz a colisão dentro do lote; ela não alcança quem está fora dele.

**Lote 9 — 25/08/2026** (Lote 4 da Caixa: EVO-40 · EVO-42 · EVO-41 em **fila interna** na mesma célula, mais 7 PRs da maestro; PRs #182–#198, 11 merges, 2 deploys verdes, 0 revert, 1 passo do mantenedor executado de primeira — e o lote **descobriu cinco defeitos fora do seu assunto**, um deles no próprio portão de merge):

1. **A pergunta ao mantenedor pode voltar mudando o desenho do lote — e isso é lucro, não
   ruído.** Perguntei duas coisas de múltipla escolha (CLAUDE.md, formato que ele confirmou).
   Na primeira ele escolheu a opção **mais travada** das três, sabendo do custo. Na segunda
   **não escolheu nenhuma**: pediu uma coisa maior — notificar todos os que interagiram com
   a ideia, com sininho estilo rede social, avisando que *"serão muitas"*. O lote passou de 2
   para 4 frentes na hora. **Regra: quando a resposta transborda a pergunta, reescreva a
   composição antes de despachar** — e separe, no mesmo relatório, o que cabe agora do que
   é rito (aqui, o sininho fora da Caixa exige contrato congelado ⇒ Rito §3 com ele
   presente, nunca em lote). Dizer isso na hora é o oposto de cortar escopo: é nomear o
   caminho certo.

2. **Decisão do mantenedor vira PR de lei ANTES do despacho que a implementa — e o PR
   precisa dizer o que a garantia NÃO é.** A `DECISAO-EVO-40` mergeou antes de uma linha de
   código (lição 32 do Lote 6, aplicada de propósito). O que ela acrescentou ao padrão:
   escrever, **com todas as letras, que o fail-closed é o comportamento certo e não um
   defeito**, para que nenhuma sessão futura o "conserte"; e escrever que a célula **não
   verifica** o documento do ChangeSpec — a garantia é *"alguém autorizado afirmou, e ficou
   registrado quem e quando"*. Sem essa frase, o próximo agente supõe uma verificação que
   não existe.

3. **Teto de despacho: declarar um invariante novo custa DOIS arquivos, não um.** O EVO-40
   fechou em 16 (teto 15) porque `INVARIANTES.md` + a linha do inventário de códigos em
   `ci/tests/test_guarda_dos_guardas.py` andam juntas — sem a segunda, `--apenas testador`
   fica vermelho. **A calibragem errada foi do brief, não do agente**, que fez o certo:
   declarou o estouro em vez de espremer. A válvula (label `arquitetural`) foi aberta **com
   o motivo comentado no PR**, porque válvula usada em silêncio vira válvula usada sempre.
   Injetei o custo no brief do elo seguinte, e ele fechou em 10/15.

4. **Um lote que mexe em provisionamento tem de auditar o provisionamento — e foi ali que
   estava a mina.** Ao acrescentar UMA variável de ambiente, o agente de infra conferiu se
   ela precisaria entrar no gerador e achou de brinde que o `provisionar-sugestoes.sh`
   **reescreve o env inteiro** e não conhece duas chaves que o login pôs lá no dia anterior:
   re-rodá-lo deixaria a porta da Caixa em **HTTP 500 para todo visitante, com o pipeline
   verde**. O projeto já sabia do risco — **em comentário dentro do próprio heredoc**, que é
   garantia sem mecanismo. Virou trava de deriva nos **três** scripts da família (o terceiro
   pela sessão vizinha, avisada), com guarda que reprova se a lista e o heredoc divergirem.

5. **Sessão vizinha não é ruído a evitar: é par a avisar, e o retorno paga o aviso.** Medi
   que o PR em voo dela criava o **terceiro** script da mesma família, sem a trava. Mandei
   uma mensagem com o bloco pronto, dizendo que a decisão era dela. Ela fechou a trava **e**
   pôs o script na lista do guarda no MESMO PR — e devolveu duas coisas que eu não tinha:
   (a) uma consequência da minha própria mudança no script da identidade, que eu não tinha
   enxergado; (b) uma medição do cache do `raw` **oposta à minha**. Custou uma mensagem.

6. **Duas medições opostas do mesmo fenômeno valem mais que dez iguais — e a
   intermitência é a lição.** O `raw.githubusercontent.com/.../main/...` (o endereço da linha
   que entregamos ao mantenedor) tem `Cache-Control: max-age=300`. Na minha medição serviu a
   versão **antiga** por mais de dois minutos; na da sessão vizinha, `Source-Age: 0`, versão
   nova imediata. **Isso torna a armadilha pior, não melhor:** quem testar uma vez e vir
   fresco conclui de boa-fé que o problema não existe. Por isso a regra registrada não é
   "espere 5 minutos" — é **"confira o conteúdo servido, não o relógio"**, com um `curl |
   grep <marca da versão nova>` antes de entregar a linha. `armadilhas/112`.

7. **O portão de merge pode reprovar o que está verde — e isso é mais grave que reprovar
   demais.** Aplicar a label `arquitetural` re-dispara o `muralhas` (evento `labeled`), e o
   GitHub mantém **as duas execuções** penduradas no mesmo SHA. O `mergear.py` emitia um
   veredito por entrada e reprovava para sempre, enquanto `gh pr checks` dizia `pass` no
   mesmo instante. **Portão que reprova quem está certo ensina a ser contornado** — e o
   único caminho que sobra é o botão do site, exatamente o que ele existe para tornar
   desnecessário. Conserto: desduplicar por nome pela hora, com desempate **fail-closed**
   (sem hora ou hora igual ⇒ fica a PIOR).

8. **Em teste de "pegue o mais recente", monte um caso com a ordem INVERTIDA — senão o
   guarda testa a fixture.** Das quatro mutações que fiz no conserto acima, **uma passou**:
   trocar a comparação de hora por `if True` (= "fica com a última entrada percorrida")
   deixava a suíte verde, porque todas as minhas fixtures tinham o rerun no fim da lista. A
   API não promete ordem nenhuma. Fechei com dois casos de ordem trocada. **Quem escreveu o
   guarda é quem menos enxerga a premissa dele.**

9. **Merge que devolve 502 não é merge que falhou — vá ler o estado.** O GitHub respondeu
   `502 Bad Gateway` no meio de um merge. O commit **entrou** na `main`; o que falhou foi o
   passo que fecha o PR, que ficou `OPEN` com diff vazio. **O portão se comportou certo: não
   declarou sucesso** — morreu ruidosamente em vez de imprimir "mergeado" por otimismo. A
   maestro confirmou por três vias (`git log origin/main`, `git branch -r --contains`, diff
   vazio) e fechou o PR à mão com o registro. `ERROR` continua sendo "não medi", nunca
   "falhou".

10. **Auditoria de fechamento acha defeito no DOCUMENTO, e isso vale tanto quanto bug.** Os
    cinco vereditos do EVO-41 não tiveram um FAIL de código — e mesmo assim o despacho foi o
    mais valioso do lote. Ele achou que a spec **se contradiz** (§8 lista o invariante do
    merge sem ressalva, §10 põe merge em V1.1, §11 exige "todas as da §8" para o MVP: a DoD
    era impossível de cumprir ao pé da letra); que o §11 pedia um `403` que **quebraria outro
    guarda** se implementado; e que o AS-IS ainda afirma *"não existe login de usuário final
    em nenhuma célula"* — hoje falso, com a célula `identidade` no ar. **Documento que mente
    com autoridade custa mais caro que código errado**, porque o próximo agente não
    desconfia dele. A cura do AS-IS foi **tarja de data, não reescrita**: ele é o registro do
    que se sabia na hora da decisão, e é o anexo que a própria DoD exige.

**Lote 8 — 25/08/2026** (5 despachos em paralelo — EVO-31 da Caixa, o buraco (a) da AUD1 e as peças B2/B3/C3 do PLANO-10X; PRs #171–#175 mais o #178 de fechamento da maestro; 6 merges, 1 deploy verde, 0 revert; rodou ao lado de OUTRA sessão que mergeou **três** PRs, dois deles no `CLAUDE.md`):

1. **Achado de auditoria é hipótese até alguém rodar a mutação — inclusive quando a
   auditoria já foi feita POR mutação.** A AUD1 (lição 5 do Lote 4 de 25/08) usou prova
   por mutação e mesmo assim descreveu o buraco (a) errado: dizia que apagar o router
   `checkout-api` do Traefik "continua verde no CI". A maestro reproduziu num worktree
   descartável antes de escrever o brief e mediu o contrário — apagar fica **vermelho**,
   porque um teste vizinho mantém um inventário de nomes de rota. O buraco real era outro
   e mais afiado: `priority: 20 → 0` e `service: checkout → funil` **quebram a venda com
   270 testes verdes**. O despacho inteiro mudou de forma por causa de quinze minutos de
   medição. **Regra: item de lote que nasce de um achado escrito é REPRODUZIDO pela
   maestro antes do brief, não depois.** O custo é um worktree; o de não fazer é despachar
   um agente para consertar o que não está quebrado — e deixar aberto o que está.

2. **A superfície medida vence a fila herdada — "mesma pasta" não é a cerca, a lista de
   arquivos é.** O painel do PLANO-10X prescrevia B3 → B2 → C3 em **fila interna**, "porque
   os três moram em `ci/`". Contando arquivo a arquivo no papel (§2.2), as superfícies são
   **disjuntas**: B3 = `alarme-main.yml` + `esqueleto.sh`; B2 = `ci/ci.py` + arquivos novos;
   C3 = `Makefile` + arquivos novos. Os cinco rodaram em paralelo e **não houve uma única
   colisão de código** — só a do arquivo gerado (lição 3). O que tornou isso seguro não foi
   otimismo: foi cada brief trazer a lista fechada de alvos, os arquivos dos irmãos
   nomeados como SOMENTE-LEITURA, e a ordem "precisou de outro arquivo? PARE e reporte".
   Serializar por diretório teria custado três rodadas inteiras de calendário.

3. **Com N despachos que produzem armadilha, quem numera é a MAESTRO na janela — não o
   agente no push.** A lição 1 do Lote 4 ("escolha o número imediatamente antes do push")
   não basta quando três PRs terminam juntos: neste lote **três** reivindicaram o `106`, e
   antes disso dois reivindicaram o `104`. O que funcionou foi atribuir nominalmente depois
   do primeiro merge — "o 106 ficou com o #173, você fica com o 107, o #175 fica com o 108"
   — em mensagem a cada agente, junto com a ordem de resolver conflito de índice **só**
   por `python ci/indice_de_armadilhas.py`. Duas rodadas de renumeração viraram uma.
   **Corolário:** ao mandar renumerar, mande **conferir em disco depois do rebase** em vez
   de confiar no número atribuído — foi o que os dois agentes fizeram, e é o que impede a
   atribuição da maestro de virar mais uma fonte de erro.

4. **O card do plano é o PEDIDO; a medição é a lei — e "mais estreito por medição" não é
   escopo reduzido.** O card do B3 mandava rodar as três muralhas na `main`. O agente mediu
   e provou que só uma faz sentido: num push da `main` o diff é vazio, então cerca e
   orçamento passariam **por vacuidade** (falso-verde), e dar-lhes base real não salva
   porque as duas julgam por `PR_LABELS`, que não existe fora de um PR — todo merge de
   contrato e toda mudança arquitetural legítimos abririam issue de "main vermelha".
   Entregou a guarda de segredos (a única repo-wide), com o SKIP das outras duas
   **declarado por escrito no YAML e executável por teste**. Isto **não** contradiz a lei
   de 25/08 ("nunca proponha a versão minimalista"): o que ela proíbe é encolher para
   poupar esforço. Estreitar porque a medição prova que o mais largo é *nocivo* é a
   entrega certa — e a diferença entre as duas coisas é sempre a evidência colada.

5. **Vermelho que só existe na máquina do agente é dívida silenciosa — e tem dono.** O
   varredor de referências entrava em `.claude/worktrees/` (worktrees velhos do harness) e
   achava lá a sentinela do próprio fixture: `pytest ci/tests` reprovava no clone principal
   e passava no runner do GitHub. Invisível na CI, barulhento para quem trabalha — e
   vermelho que todo mundo aprende a ignorar é como um guarda morre. O que fez isso sair
   barato foi **rotear para o despacho que ia reimplementar o mesmo varredor** (o B2, que
   precisava andar na árvore atrás de `test_inv_*`): ele consertou na fonte
   (`git ls-files --cached`), num varredor único, e o consertado **achou uma referência
   pendurada de verdade** na própria suíte nova dele. Injete o aviso "isto é ambiente, não
   é seu, não conserte" nos briefs que NÃO são donos, e o conserto no brief de quem é.

6. **Dívida que o agente declara em vez de contornar é trabalho da maestro no mesmo lote —
   e o registro bem escrito é que a torna barata.** O despacho do C3 topou com um defeito
   fora do mandato dele (`ci/ci.py` lendo o exit 2 do GNU Make como ERROR, ou seja,
   reprovação de célula reportada como "não consegui medir"). Ele não tocou no arquivo —
   estava com outro despacho — e escreveu sintoma, causa e mecanismo em `armadilhas/107`.
   A maestro fechou no PR de fechamento (#178) no mesmo dia. **E a armadilha estava errada
   num ponto que só apareceu ao implementar:** ela dizia "a correção é de uma linha", e não
   é — trocar `1` por `!= 0` consertaria a reprovação e quebraria o outro lado, porque o
   make devolve 2 **também** para alvo inexistente, que é ERROR de verdade. Foi preciso um
   ensaio (`make -n`) para separar as duas metades, porque ler a mensagem do make dependeria
   do locale do runner. **Regra: a estimativa dentro de uma armadilha é palpite de quem não
   implementou — corrija-a na entrada quando fechar a dívida**, senão o próximo despacho
   herda o palpite como fato.

7. **A maestro cai nas armadilhas que a própria casa escreveu — e a defesa é hábito, não
   conhecimento.** Duas vezes neste lote: (a) ao provar a catraca do B2, li `echo $?`
   depois de um `| tail` e recebi **0** de um portão que devolvera **1** — é a §5.10, escrita
   neste repositório, e ela pega quem a conhece; (b) escrevi aspas retas dentro de uma
   string do `painel-dados.js` e quebrei o painel, que é a irmã da lição 3 do Lote 4. As
   duas foram apanhadas por **procedimento**, não por atenção: exit sempre medido sem pipe,
   e `node --check` depois de TODA edição de painel. **Saber a armadilha não protege;
   executar o passo protege.**

**Lote 4 — 25/08/2026** (5 despachos em paralelo + 3 PRs de fechamento da maestro; PRs #160–#163, #166–#167; 7 merges, 4 deploys verdes, 0 revert; rodou ao lado de OUTRA sessão que mexia na célula `funil`):

1. **O arquivo gerado é o ponto de colisão previsível do lote — numere por último.**
   `armadilhas/INDICE.md` é regenerado por script e conflita em TODO rebase; pior, o
   próximo número livre muda a cada merge da janela. A entrada do EVO-30 nasceu 099 e
   fechou em **102**, renumerada três vezes. Quem pegou as colisões foi o próprio
   `ci/indice_de_armadilhas.py`, que recusa número repetido e diz qual renomear — o
   mecanismo funcionou. Regra para o próximo brief: **escolher o número da armadilha
   imediatamente antes do push**, nunca no começo do trabalho; e resolver conflito de
   índice sempre por `python ci/indice_de_armadilhas.py`, jamais editando o índice à mão.
2. **Agente que lê o trabalho dos irmãos evita duplicata sozinho.** O despacho de `alunos`
   percebeu que o de `quiz` (PR irmão, mesma classe de conserto) já tinha criado a
   armadilha da classe e **não criou a sua** — registrou só o que era particular da
   célula. Vale injetar no brief de lotes com conserto repetido em N células: “a classe
   se cataloga UMA vez; o resto vai no `LICOES.md` da célula”.
3. **`arquivos/` (os painéis) é do maestro, e isso precisa estar no brief.** Como a pasta
   é gitignored, ela **só existe no clone principal** — agente em worktree não a enxerga,
   e duas sessões editando o mesmo `painel-dados.js` no clone principal se atropelam sem
   que o Git perceba. Nesta sessão a própria maestro quebrou o painel com um item
   multilinha (`armadilhas/095`) e desfez pelo backup. Proibir `arquivos/` em todo brief
   e fechar o painel no §6 funcionou: zero colisão em 5 despachos.
4. **ERROR no portão de merge é instrumento, não código — repita a medição.** Logo após um
   merge, o `mergear.py` do PR seguinte devolveu **ERROR** (o GitHub ainda calculava
   conflito de forma assíncrona). A resposta certa é esperar e rodar de novo; 25 segundos
   depois veio PASS. Forçar o merge ou “consertar” algo aí seria criar problema onde não
   havia (regra 5 do §3, [INV-CI01]).
5. **Auditoria só-leitura é a frente mais barata de rodar em paralelo — e a que mais
   descobre.** A AUD1 não abre PR, não mergeia e não disputa arquivo com ninguém: colisão
   zero por construção. Foi ela que fechou a Onda 1 do PLANO-10X **e** achou os 4 buracos
   de cobertura (§9 do `ARMADILHAS-OPERACAO.md`). O método que produziu o valor foi
   **prova por mutação** em worktree descartável: quebrar o código de propósito e exigir
   que a suíte fique vermelha. Injete isso em todo brief de auditoria — “desconfie de
   teste que passa mas nunca poderia falhar” só vira evidência quando alguém tenta.
6. **Lote roda ao lado de sessão alheia se a superfície for medida antes.** Uma outra
   sessão trabalhava na célula `funil` e em 3 documentos; o lote foi composto só com
   células fora dessa lista e não houve um único conflito. Medir a superfície da sessão
   vizinha (`gh pr view --json files` + `git status` do worktree dela) é parte da
   montagem do §2, não cortesia.

**Lote 1 — 22/08/2026** (6 despachos, 8 PRs #61–#68, 8 merges, 8 deploys verdes, 0 revert):

1. **A pilha de `git stash` é ÚNICA por repositório — compartilhada por todos os
   worktrees.** Duas sessões usando o protocolo vermelho→verde por stash (§6.1 do
   ARMADILHAS) ao mesmo tempo poparam o stash uma da outra. Ninguém perdeu trabalho,
   mas custou uma investigação no meio da janela. Regra nova (ARMADILHAS §6.1.1):
   em lote, evidência vermelho→verde por **patch**, nunca stash — e a maestro deve
   INJETAR essa regra em todo brief (regra 3 do §3).
2. **Recursos locais compartilhados se pré-atribuem no brief.** Porta de Postgres/Redis
   exclusiva por despacho (55433, 55434, …), nome de container exclusivo — zero colisão
   em 5 células paralelas. Sem isso, todos usariam o 55432 do ARMADILHAS §2.
3. **Convenção transversal se dita no brief, não se negocia depois.** As três células
   que mexeram com Huey e o despacho de infra convergiram sem coordenação em tempo real
   porque TODOS os briefs traziam a mesma frase ("worker sobe com `manage.py run_huey`;
   env de Redis nunca fail-hard no import"). O custo de escrever a convenção uma vez é
   muito menor que o de reconciliar quatro desenhos divergentes na janela de merge.
4. **Na janela de merge, `--conferir | tail && --confirmo` mascara o exit do primeiro
   comando** (§5.10 do ARMADILHAS, versão da maestro). Inofensivo aqui porque o
   `--confirmo` reconfere tudo por construção — mas o hábito certo é rodar o
   `--confirmo` sozinho ou capturar o exit antes do pipe.
5. **Conflito entre PRs da MESMA célula na janela é normal e barato**: o GitHub recalcula
   (`mergeable: UNKNOWN` → espere; `CONFLICTING` → o agente daquele PR rebaseia e o
   portão roda de novo). Custou ~5 minutos e funcionou exatamente como o §5 previa.
6. **Sequenciar dependências por ordem de merge funciona**: o PR de infra que liga
   workers novos (`run_huey`) mergeou por último, depois dos deploys verdes das células
   que ele referencia — nenhuma janela de incompatibilidade em produção.

**Lote 2 — 22/08/2026** (5 despachos, PRs #71–#75, 5 merges, deploys verdes — o último
após incidente externo):

7. **A convenção ditada precisa incluir a SEMÂNTICA do instrumento, não só nomes.**
   As 4 células convergiram no mesmo desenho, mas três descobriram de forma
   independente a mesma nuance (`XAUTOCLAIM` incrementa o delivery_count e não o
   devolve — o número que decide fila morta vem do PEL). Se o brief tivesse ditado
   isso, teriam sido três rodadas vermelhas a menos.
8. **Mudança de DNS/proxy no meio do dia vira incidente de deploy HORAS depois.**
   O Cloudflare na frente do domínio matou o SSH do pipeline (`VPS_HOST` guardava o
   domínio) só quando o cache de DNS venceu: 4 deploys verdes e o 5º vermelho no
   MESMO lote. Mudou DNS/proxy de host que pipeline usa ⇒ teste o canal do pipeline
   imediatamente (ARMADILHAS §3.17). O diagnóstico certo levou 2 reruns: o 1º
   rerun reprovando IGUAL foi o que separou "blip de rede" de "causa estrutural".
9. **`mergeable: UNKNOWN` logo após o merge anterior é rotina da janela**, não
   anomalia: espere o recálculo do GitHub (loop até sair de UNKNOWN) antes de
   acionar o portão — duas ocorrências neste lote, zero dano.

**Lote 3 — 23/08/2026** (4 despachos, PRs #86–#89, 4 merges, 2 deploys verdes, 0 revert
— o primeiro lote com **fila interna** de 3 fases na MESMA célula, guiado por um
documento de decisão aprovado no mesmo dia):

10. **Fila serial na mesma célula ACELERA quando cada fase entrega baseline para a
    seguinte.** As fases 1→2 do funil não podiam ser paralelas (cerca 1 PR = 1 célula).
    Mas a fase 2 nasceu do commit já EM PRODUÇÃO da fase 1, herdou os 81 testes dela
    como baseline e o teste *golden* byte-idêntico como cinto de regressão — e saiu em
    22 min contra 38 da fase 1, com escopo maior. Sequenciar não foi o custo da cerca;
    foi o que deu velocidade. **Regra:** ao dividir uma entrega grande em fases na mesma
    célula, faça a fase N terminar deixando *portões* que a fase N+1 herda, não só código.
11. **Pendência devolvida por um despacho é DECISÃO no brief do seguinte — nunca
    pergunta ao humano.** A fase 1 devolveu duas em aberto (canal do POST de site
    prefixado; helper de URL com idioma). A maestro decidiu as duas no brief da fase 2
    (postar na própria URL prefixada — o que de quebra capturou o idioma do lead; e
    promover o helper a template tag com lint). Nenhuma foi ao mantenedor, nenhuma
    virou dívida. Perguntar teria custado uma rodada de conversa por pendência.
12. **Brief que manda VERIFICAR antes de documentar encontra divergência entre a lei e
    o código.** O despacho da receita exigia "confira no código real antes de afirmar
    qualquer coisa, e diga no PR quais arquivos leu". Resultado: três divergências entre
    o plano aprovado e a implementação — inclusive uma **ativa e perigosa** (o marcador
    `_juridico` que o plano manda usar reprova o catálogo e, como o validador roda no
    boot, derruba a célula — ARMADILHAS-OPERACAO.md §9). Sem essa exigência, a receita teria
    descrito um sistema imaginário e o próximo agente executaria o comando que quebra.
13. **Documento aprovado não é código — audite-o no fim do lote.** Um plano validado
    pelo mantenedor vira *lei* para os agentes seguintes, e eles não desconfiam dele.
    Quando o lote é guiado por um documento de decisão, o ÚLTIMO despacho deve auditar
    documento×realidade e registrar cada divergência (aqui: portão que mora no `make ci`
    e não em `ci/`, marcador inexistente, semântica de `pendente` mais ampla que a
    descrita). Custa um parágrafo no brief; evita que a próxima sessão trate promessa
    como fato.
14. **Lote que muda site ao vivo só fecha com prova MEDIDA DE FORA.** CI verde e deploy
    verde não provam que a URL responde — provam que o pipeline rodou (a lição do H13
    vale aqui). O fechamento honesto foi `curl` na internet pública contra a matriz
    inteira (raiz→302, os três idiomas, prefixo inválido→404, POST nu→404, sitemap,
    hreflang) **e contra um site legado**, para provar no mundo real o que o teste
    *golden* prova no CI: quem não entrou no regime novo não mudou.


**Lote 4 — 23/08/2026** (2 despachos paralelos, PRs #94–#95, 2 merges, 1 deploy verde,
0 revert — o lote das *dívidas declaradas* do Lote 3, e o primeiro a conviver com outra
sessão mergeando na mesma `main`):

15. **Dívida que o lote anterior declarou vira o lote seguinte — e sai barata.** Os dois
    despachos aqui nasceram de pendências que o Lote 3 registrou em vez de contornar
    (`docs/historico/RESOLVIDAS.md` §5.11 e a linha do `_juridico` na §9 do
    `ARMADILHAS-OPERACAO.md`). Porque a dívida estava escrita
    com sintoma, causa e solução, os briefs saíram quase prontos e os dois despachos
    couberam no orçamento sem investigação. **Corolário:** o custo de registrar uma
    dívida bem descrita é pago pelo despacho que a fecha, não pelo que a descobriu.
16. **Toda regra copiada entre dois portões precisa de guarda mecânica contra deriva.**
    A §5.11 nasceu porque `orcamento-de-mudanca.sh` e `mergear.py` implementam a mesma
    regra de propósito (portão + catraca, Escada da Imposição) e uma evoluiu sem a outra.
    O conserto não foi só ensinar a lane à catraca: foram dois testes que **leem o
    próprio `.sh`** e reprovam se as cópias divergirem — inclusive um que vigia a
    *assimetria deliberada* (a catraca confere caminho, as muralhas conferem modo,
    porque a API de PR do GitHub não devolve modo). Duplicação consciente é aceitável;
    duplicação sem guarda é armadilha com data marcada.
17. **Marcador declarativo sem expiração é carimbo perpétuo.** O `_juridico` exigia
    "revisão humana declarada". A implementação foi além do brief e acertou: a
    declaração é **por idioma** (revisar o inglês não valida o espanhol) **e expira no
    diff** — se o texto de um idioma muda e a declaração daquele idioma não, reprova.
    É a mesma mecânica anti-burla do `_fonte`, pelo mesmo motivo: sem ela, recarimbar
    sai mais barato que cumprir. **Regra geral para qualquer marcador de qualidade
    declarado por agente: amarre-o ao conteúdo que ele atesta, ou ele vira decoração.**
18. **Peça ao agente a decisão, não a implementação, quando a escolha depende do que a
    ferramenta REALMENTE faz.** O brief de `ci/` não mandou conferir o modo dos
    arquivos: mandou **sondar a API e decidir**, justificando. O agente mediu
    (`gh pr view --json files` não traz modo), escolheu a barreira em profundidade e
    transformou a premissa em teste. Brief que decide por antecipação teria produzido
    ou um campo inventado ou uma remedição frágil.
19. **Duas sessões na mesma `main` são rotina, não incidente — se a regra anticolisão
    estiver no brief.** Outra sessão mergeou três PRs (#91–#93) durante este lote,
    inclusive tocando `ci/` e `ARMADILHAS.md`. Os dois agentes rebasearam, as entradas
    de todos sobreviveram lado a lado, e um deles precisou de `push --force-with-lease`
    na **própria** branch — o que é correto. A maestro só precisa: (a) `git fetch` no
    pré-voo e antes de cada janela; (b) desconfiar de "PR #N foi mergeado no meio do meu
    trabalho" e **conferir quem mergeou** (`gh pr view <N> --json mergedBy,headRefName`)
    antes de concluir que um agente do lote furou a janela — aqui não tinha furado.
20. **Merge que não muda comportamento também se prova de fora.** O PR do `_juridico`
    mexeu só no validador, mas dispara `deploy-celula` igual. O fechamento honesto foi
    medir a matriz pública de novo depois do deploy: nada mudou — que era exatamente a
    afirmação a provar.

**Lote 5 — 24/08/2026** (fase 4 do i18n: contrato → provedor → consumidor, PRs
#104/#106/#107, mais #109 e #112 para destravar; 1 incidente de canal de deploy, 0
revert, 0 minuto de produção derrubada — o primeiro lote a atravessar o **Rito de
Contrato** e o primeiro a travar o **canal** de entrega sem travar o site):

21. **O Rito de Contrato cabe num PR isolado — e o preço é uma janela de divergência
    que o brief tem de nomear.** Antes de mergear o contrato sozinho (#104), a maestro
    conferiu quais workflows obrigatórios rodam o portão `freeze`: `muralhas` e
    `alarme-main` medem outra coisa, e o `ci-celula` só roda o `make ci` da **célula
    tocada** — um PR que só mexe em `contracts/` não toca célula nenhuma, então a
    `main` não fica vermelha entre o contrato e o provedor. **Mas o baseline do
    provedor nasce vermelho no `make contrato-check` da célula**, que é o comportamento
    certo (o contrato mudou, a implementação ainda não). Isso **precisa estar escrito
    no brief do provedor**: sem isso o agente abre o worktree, vê vermelho no baseline
    e para achando que a `main` quebrou — gastando uma rodada de investigação para
    redescobrir a ordem do próprio rito.
22. **Dois workflows que disparam no MESMO merge não têm ordem entre si — e um
    artefato que atravessa os dois vira impasse fechado.** O `deploy-infra` injeta
    `infra/sincronizar_sites.py` (do commit recém-mergeado) dentro do container que o
    `deploy-celula` ainda vai atualizar. O script novo importou um símbolo que só
    existe na imagem nova ⇒ `ImportError` ⇒ `deploy-infra` vermelho ⇒ o
    `portao-de-deploy`, fail-closed, barrou o `deploy-celula` por
    `vermelhos-nao-previstos` ⇒ cada um esperando o outro. Produção seguiu 100%
    saudável: o que travou foi o **canal**, não o site — e o portão fez exatamente o
    que devia. **Regra geral: arquivo injetado num artefato versionado à parte só pode
    depender de símbolo que já existia na versão anterior.** Detalhe em
    `armadilhas/078`; a regra de quem rege é reconhecer a FORMA — se a resposta a
    "isso funciona?" depende da ordem de dois pipelines, a resposta é não.
23. **Impasse de pipeline não se resolve com `rerun` — resolve-se com um caminho
    NOVO.** O portão consulta `actions/runs?head_sha=<SHA>`: re-rodar o run antigo
    reavalia o **mesmo commit**, que contém o código quebrado. A sequência que
    destravou foi (a) corrigir o script (#109), (b) um PR que tocasse
    `services/catalogo/**` para o `deploy-celula` **existir** naquele SHA — aqui, a
    correção de uma lição errada no `LICOES.md` da célula (#112), **legítima e
    necessária por si**, nunca um commit de conveniência para mover o pipeline —, e
    (c) rerun do `deploy-infra` para gravar os dados já com a imagem nova. Quem rege
    precisa saber distinguir as duas coisas: se o PR-veículo não se sustentaria
    sozinho no review, o problema é outro.
24. **`i/o timeout` no SSH do runner com a VPS viva é blip, não estrutura — mas só
    depois de medir.** O reflexo (lição 8: "mudou DNS/proxy ⇒ incidente horas depois")
    apontava para causa estrutural. A medição feita antes do diagnóstico disse o
    contrário: site respondendo 200, porta 22 devolvendo o banner SSH, 443 no IP
    em 404. Um rerun
    bastou. É a §3.17 aplicada na direção difícil — **medir antes de diagnosticar vale
    inclusive para confirmar que NÃO é o incidente que você já conhece.**
25. **A catraca recusou duas vezes por não conseguir MEDIR (`ERROR`, não `FAIL`), e as
    duas vezes a resposta certa foi esperar.** Uma por consulta transitória incompleta,
    outra pelo `mergeable: UNKNOWN` que a lição 9 já descreve. Um `ERROR` da catraca
    nunca é convite a forçar: é a diferença entre "medi e reprovei" e "não consegui
    medir", e tratá-los igual destruiria a única informação que o portão tem a dar.
26. **Teto de despacho mal calibrado é erro de quem escreve o brief — e apagar arquivo
    é o caso clássico.** O despacho do consumidor recebeu teto de 10 arquivos e entregou
    14: todos os extras eram **leitores do arquivo que estava sendo apagado**
    (`sites_i18n.yaml`), e não havia como remover a fonte sem tocar quem a lia. O agente
    fez o certo — **declarou o estouro em vez de espremer**, ficou dentro do portão do
    CI (15) e explicou arquivo por arquivo. **Regra para a maestro: ao mandar apagar um
    arquivo, o orçamento tem de contar quem o lê** (`grep` antes de escrever o número),
    e a regra que o agente aplicou é a de sempre: teto apertado não justifica entrega
    pela metade — justifica declarar.

**Lote 6 — 24/08/2026** (Caixa de Sugestões, Lote 1 do plano mestre: 5 despachos em
**fila interna** na MESMA célula, PRs #108/#113/#116/#122/#126, mais #110/#119/#121/#123
de registro; 9 merges, 0 revert, 0 minuto de produção derrubada — o primeiro lote a
criar uma célula do zero, e o primeiro cujo deploy nasce vermelho de propósito):

27. **Fila interna só funciona se cada elo herdar o que o anterior descobriu.** Cinco
    despachos na mesma célula, um de cada vez. O que fez a fila andar não foi a ordem:
    foi cada brief mandar **ler o `LICOES.md` da célula** e trazer injetadas as
    armadilhas que o elo anterior achou. A do `reverse()` (achada no EVO-12a) entrou nos
    briefs do EVO-12b e do EVO-13 e não mordeu de novo. Sem isso, fila é só
    serialização — e cada agente redescobre o mesmo buraco.

28. **Dividir despacho é decisão da maestro na MONTAGEM, não do agente no meio.** O
    EVO-12 virou 12a (a porta) + 12b (a participação) **antes de qualquer agente ser
    disparado**, porque o orçamento de 15 arquivos foi contado no papel e não fechava
    com o login junto. Os dois saíram com 15/15 exatos. Deixar o agente descobrir isso
    no meio custa uma rodada e tenta a fusão de arquivos, que é anti-meta.

29. **O que não coube no orçamento do agente é trabalho da maestro, não dívida.** Três
    vezes neste lote o agente achou armadilha nova e ela não coube (entrada + índice
    regenerado estouram o teto). O padrão que funcionou: **o agente registra no
    `LICOES.md` da célula e avisa no handoff; a maestro promove para `armadilhas/` num
    PR próprio** (#119, #123, e o do fechamento). A lição não se perde e o teto não é
    burlado.

30. **Relato de agente é hipótese até alguém rodar o comando.** Um handoff afirmou que
    patch de dois arquivos "falha em silêncio sem a linha `diff --git`, e o erro aponta
    para o arquivo errado". Antes de virar entrada, a maestro reproduziu num repositório
    de teste: **nenhuma das duas metades se confirma**. O mecanismo real era outro
    (contagem de linha errada no cabeçalho do trecho), e a entrada #084 foi escrita com
    o desmentido junto. Gravar como lei o que não reproduz é pior que não gravar.

31. **Vermelho ESPERADO vai no brief; vermelho novo é lido no log — sempre.** Os cinco
    merges deixaram o `deploy-celula` vermelho de propósito (o compose da VPS só ganha a
    célula no Lote 2). Declarar isso em cada brief impediu cinco agentes de "consertar" o
    que não era deles. **Mas no terceiro merge apareceu um vermelho DIFERENTE** —
    `dial tcp :22: i/o timeout`, o runner sem alcançar a VPS. Presumir "é o de sempre"
    teria engolido uma falha de canal. Foi medido (três sites em 200, porta 22
    respondendo do PC), repetido, e voltou ao vermelho esperado. **Conferir custou dois
    minutos; presumir custaria descobrir dias depois.**

32. **Decisão de produto que aparece no meio do lote vira LEI antes do despacho que a
    implementa.** O EVO-12a achou que o contrato de `alunos` devolve `status` em
    `[ativa, suspensa, reembolsada]` e que a decisão de identidade não falava disso — e
    **parou de decidir**, registrando a lacuna. A maestro levou ao mantenedor na hora;
    ele decidiu; virou a §4.1 da `DECISAO-EVO-01` (PR #121) **antes** de o EVO-13 ser
    despachado, e o EVO-13 nasceu com o guarda que trava aquela decisão — o patch que
    "conserta" o filtro deixa o CI vermelho. Decisão que fica só na conversa evapora;
    decisão sem guarda é "consertada" pelo próximo agente de boa-fé.

33. **Gênese de célula toca TRÊS caminhos CODEOWNERS, não dois.** A auditoria dizia que
    célula nova não mexe em `.github/` — mediu `ci-celula.yml` e `deploy-celula.yml`, que
    detectam a célula sozinhos, e generalizou. O `rollback.yml` **não detecta nada** e
    tem guarda de paridade exata com o manifesto. O canário travou no `muralhas` por
    **uma linha**, e o agente de célula não podia corrigir. Corrigido na fonte (#110):
    a Q4 da auditoria e o `MODELO-DESPACHO.md` agora nomeiam os três. **Documento que
    "generaliza a partir de dois" é armadilha esperando o terceiro caso.**

**Lote 7 — 24/08/2026** (Caixa de Sugestões, Lote 2 do plano mestre: Rito de Contrato +
3 despachos, PRs #128/#130/#129/#133, mais #131/#132/#134 de ferramenta; 7 merges,
0 revert, 0 minuto de produção derrubada — o primeiro lote a **pôr uma célula nova no
ar** e o primeiro em que o passo do mantenedor falhou TRÊS vezes antes de dar certo):

34. **A ordem de merge entre células é achado de despacho, não palpite da maestro.** O
    agente de infra descobriu sozinho que o PR dele **não podia** entrar antes do PR da
    célula: o compose declarava `sugestoes-relay` rodando `manage.py run_huey`, e a
    imagem daquele momento não tinha o Huey. Mergear na ordem errada faria o serviço
    subir como `Unknown command` e **reprovar a verificação da plataforma inteira**, não
    só da célula nova. Ele escreveu isso no handoff; a maestro obedeceu e conferiu passo
    a passo que a imagem nova saíra antes (o step *Build & push* verde dentro de um run
    que falhou na ativação). **Peça ao agente de infra a ordem, sempre — ele leu o
    compose, você não.**

35. **Convenção ditada nos DOIS briefs é o que deixa despachos paralelos convergirem.**
    `sugestoes-relay` + `python manage.py run_huey` + `SCRIPT_NAME=/forms/sugestoes`
    foram escritos, iguais, no brief da célula e no de infra — que rodaram ao mesmo
    tempo, sem se falar. Encaixaram de primeira. É a lição 3 do Lote 1 aplicada de
    propósito, e continua sendo o truque mais barato de regência que existe.

36. **O passo do mantenedor é software, e software se testa antes de entregar.** O
    bloco de colar falhou TRÊS vezes seguidas, cada uma por um motivo diferente, e
    nenhuma por culpa dele: (a) `set -euo pipefail` + `exit` dentro de um shell
    interativo **matou a sessão** dele; (b) o console **embaralhou** a colagem
    multi-linha e o script rodou pela metade; (c) o env nasceu `root:root 600` e o
    usuário do pipeline não conseguiu ler. A cura foi parar de entregar texto: o passo
    virou **script versionado** (`infra/provisionar-sugestoes.sh`), invocado por uma
    linha curta, com guardas provados fora da VPS antes de chegar nele. **Se você vai
    pedir que um humano cole algo, escreva como script, teste os guardas, e entregue o
    endereço — não o corpo.**

37. **Segredo em argumento de linha de comando vaza pelo caminho mais natural que
    existe: o print que a pessoa manda para provar que funcionou.** A regra
    "segredo não passa por chat com agente" já estava escrita (INV-P8) e a **ferramenta
    a contradizia**. Corrigido com `read -s`, e o id do cliente segue como argumento de
    propósito — ele é público. **Regra: separe o que é público do que é segredo no
    desenho do comando; tratar tudo como segredo cansa, tratar tudo como público vaza.**
    Ver `armadilhas/090`.

38. **Vermelho esperado não dispensa ler o log — dispensa consertar.** Sete
    `deploy-celula` seguidos vermelhos com a mesma linha, todos previstos e declarados
    nos briefs. **A maestro leu o log das sete vezes**, e foi assim que apareceram os
    dois que NÃO eram o de sempre: um `i/o timeout` de SSH (Lote 1) e o
    `permission denied` do env (este lote). Os dois teriam passado por "é o de sempre".
    O custo de conferir é um comando; o de presumir é descobrir dias depois.

39. **Portão que reprova ANTES de trocar vale mais que portão que avisa depois.** O
    `deploy-infra` recusou o compose novo na validação — `ERRO: ... NADA foi trocado` —
    e a plataforma seguiu servindo os três sites em 200 durante a falha. O modo de falha
    dele é "não instalou", nunca "instalou quebrado". É o que tornou possível errar três
    vezes num passo de produção **sem um minuto de site fora do ar**.

40. **Contagem de testes que CAI entre dois verdes é sinal de trabalho perdido.** O
    agente do sininho viu `217 passed` virar `216 passed` e foi atrás: o patch de prova,
    gerado com `git diff`, tinha levado junto uma correção ainda não commitada, e o
    `apply -R` a apagou em silêncio. **Verde não significa "nada se perdeu"** — teste que
    some junto com o código dele não reprova nada. Compare a contagem com a do início do
    despacho, sempre. Ver `armadilhas/092`.

---

*Relacionados: RITOS.md (§1 abertura, §2 catraca e merge), CONSTITUICAO.md (Lei 4),
CLAUDE.md (merge pelo agente; deploy pós-merge), CAMINHO-DOURADO.md §2 (template de
brief), PLANO-10X (Alavancas 1, 2 e 5; anti-metas), ARMADILHAS-OPERACAO.md (§5.9 — como
se mergeia) e `armadilhas/` (§5.10, §7.6, §8.1 — abra pelo `armadilhas/INDICE.md`).*
