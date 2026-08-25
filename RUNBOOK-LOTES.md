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

1. **Fonte da fila:** o pedido do mantenedor > painel (`arquivos/painel-fundacao.html`,
   caixa "Precisa de você agora") > PLANO-10X (ondas). O pedido dele é o **mandato** —
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

1. **Painel** (`arquivos/painel-fundacao.html`): cada PR, cada deploy, incidentes da
   janela — sem perguntar antes (CLAUDE.md).
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
