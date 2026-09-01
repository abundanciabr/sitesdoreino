# MODELO DE DESPACHO — Caixa de Sugestões

> Template padrão para todo despacho desta iniciativa. A sessão-maestro copia,
> preenche os `<campos>`, apaga as instruções em itálico e cola para o agente.
> Herdado do formato da casa (ver `docs/decisoes/DESPACHO-04-deploy-infra.md`
> como exemplo real) + as regras do `RUNBOOK-LOTES.md`.
>
> **Antes deste molde vem o caminho:** [`DA-IDEIA-A-OBRA.md`](DA-IDEIA-A-OBRA.md)
> (estação 5). Este documento é o brief de UM agente; lá está de onde o brief
> nasce e o que precisa estar decidido antes de ele existir.
>
> Arquivo preenchido vai para `docs/caixa-de-sugestoes/despachos/DESPACHO-EVO-NN-<apelido>.md`
> — assim o histórico de cada despacho fica versionado ao lado do plano.

---

# DESPACHO — EVO-NN: <título curto, em linguagem de resultado>

> **Copie tudo abaixo da linha e cole para o agente.**
> Criado em <data> · Lote <N> do PLANO-MESTRE · merge: **agente** (Lei 4)
> *— se tocar caminho CODEOWNERS, escreva aqui o mandato e a obrigação de
> anúncio nominal no relatório final.*

ÁREA: `services/<celula>/` *(ou `infra/`, `.github/`…)* · WORKTREE: `wt-<celula>-<tarefa>`

ANTES: leia `ARMADILHAS.md` §2 (partida rápida) + `armadilhas/INDICE.md` (abra só as
entradas que casarem com esta tarefa), `services/<celula>/LICOES.md` (se existir),
<documentos específicos desta tarefa — só os necessários; agente afogado em
documentação erra mais (RUNBOOK §3.3)>. Declaração de abertura (RITOS §1) e
baseline `make ci` VERDE antes de tocar qualquer arquivo.

## CONTEXTO

*2–5 frases: por que este despacho existe, o que ele destrava, onde ele se
encaixa no PLANO-MESTRE. Cite o atrito ou o item da spec que ele resolve.*

## MISSÃO

*1 frase. Se precisar de duas, o despacho está grande demais — divida.*

## ESPECIFICAÇÃO (decisões já tomadas — siga; desvio é issue `arquitetura:`)

1. *Cada decisão de desenho já fechada, numerada, com o porquê em uma linha.*
2. *…*

## ARMADILHAS INJETADAS (as desta tarefa, não o catálogo inteiro)

- *ex.: consumer de evento ⇒ ARMADILHAS §4.8 + §4.12 (cole o bloco de código correto)*
- *ex.: schema Ninja com nome de model ⇒ §4.1 (importe com alias)*
- *ex.: script `.sh` ⇒ §3.12 (LF no blob, confira com `git show`)*

## SE O DESPACHO FOR GÊNESE DE CÉLULA — os 3 caminhos CODEOWNERS obrigatórios

Célula nova **não existe de ponta a ponta** sem estes três, e os três são CODEOWNERS:

1. `ci/manifesto-de-contratos.json` — declarar a célula (o portão reprova célula em
   `services/` fora do manifesto, e declaração órfã no sentido inverso).
2. **`.github/workflows/rollback.yml`** — acrescentar a célula em `options:`. O
   workflow **não** detecta células (choice do Actions não aceita lista dinâmica) e
   há teste-guarda exigindo paridade exata com o manifesto. **Sem esta linha a
   célula nasce sem rollback**, e o merge trava no `muralhas`.
3. `constituicoes/AGENTS.<celula>.md` — a constituição da célula.

Os três no **mesmo PR** (o guarda do rollback reprova nos dois sentidos, então
separar em dois PRs deixa a `main` vermelha no meio). **Escreva o mandato no brief**
e exija o anúncio nominal no relatório. Aprendido no PR #108 (gênese da
`sugestoes`), onde o item 2 faltava e travou o merge: `ARMADILHAS-OPERACAO.md` H17.

Orçamento: gênese passa dos 15 arquivos por natureza — abra o PR **já** com a label
`arquitetural` (adicionar depois faz o check rodar com `PR_LABELS` vazio).

## ALVOS (PERMITIDO ESCREVER) — orçamento contado: <N>/15 arquivos

- `caminho/arquivo1` *(novo | editar)*
- …

*Conte NO PAPEL antes de escrever o brief. Estourou por coesão legítima ⇒
pare e avise a maestro, nunca esprema arquivos (RUNBOOK §3.7).*

## FORA DE ESCOPO

- *Lista explícita — inclusive o que parece adjacente e tentador.*
- Pagamentos/checkout/Mercado Pago: **sempre fora**, em todo despacho desta iniciativa.
- **NÃO toque em `arquivos/painel-*.html`** — são lápides desde a reforma de
  26/08/2026. O que você DEVE fazer ao terminar é acrescentar um registro novo
  em `painel/registros/` (molde em `painel/LEIA-ME.md`) — só o registro: o
  painel gerado é materializado pela integração desde a Onda 3.

## REGRAS ANTICOLISÃO (se o lote tiver despachos em paralelo)

- Arquivo de texto compartilhado (`ARMADILHAS.md`, manifesto…): escreva SÓ a
  própria linha; `git fetch origin && git rebase origin/main` antes do push;
  conflito de proximidade ⇒ as duas linhas sobrevivem.

## DoD

**Antes do merge (você prova, com saída colada — "deveria funcionar" não é evidência):**
- [ ] `make ci` verde no worktree — cole inteiro
- [ ] *cada critério de aceitação, verificável objetivamente*
- [ ] *evidência vermelho→verde do teste-guarda novo (mostre-o falhando antes do fix)*
- [ ] Lição registrada (`ARMADILHAS.md` se serve a qualquer célula; `LICOES.md` da célula se não)

**Depois do merge (a maestro confere):**
- [ ] PR mergeado por `python ci/mergear.py <N> --confirmo <N>` (state=MERGED conferido)
- [ ] Se disparou deploy: veredito REAL por `gh run view <id> --json status,conclusion`
- [ ] `ANDAMENTO.md` + painel atualizados na mesma resposta

## PROTOCOLO DE STATUS (como reportar)

Relatório final do agente, nesta ordem: resultado em 1 frase de gente ·
placar (PR, portão, evidências) · o que ficou de fora e por quê · lições ·
o que precisa do humano (se algo — em bloco único de colar, janela rotulada).
