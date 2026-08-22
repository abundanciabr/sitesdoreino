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

---

*Relacionados: RITOS.md (§1 abertura, §2 catraca e merge), CONSTITUICAO.md (Lei 4),
CLAUDE.md (merge pelo agente; deploy pós-merge), CAMINHO-DOURADO.md §2 (template de
brief), PLANO-10X (Alavancas 1, 2 e 5; anti-metas), ARMADILHAS (§5.9, §5.10, §7.6, §8.1).*
