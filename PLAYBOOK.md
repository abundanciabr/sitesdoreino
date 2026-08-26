# PLAYBOOK — Orientação para Agentes de IA

> **Para quem:** qualquer sessão de IA (Claude Code ou outra) que abra este
> repositório — inclusive depois de troca de conta ou de máquina. Este documento
> não substitui `CONSTITUICAO.md`, `RITOS.md`, `INVARIANTES.md` ou
> `CAMINHO-DOURADO.md` — é o MAPA que diz qual deles ler, quando, e o que já é
> fato consumado vs. o que ainda está em aberto. Leitura: ~6 minutos.
>
> Se você é uma sessão de **root window** (clone principal, não um worktree de
> célula): leia isto inteiro. Se você nasceu dentro de um worktree de célula
> (`wt-<celula>-<tarefa>`), seu despacho já cita o que você precisa — mas a
> §2 e a §9 abaixo valem para você também.

## 0. O que é este projeto, em 1 parágrafo

Uma plataforma de venda de cursos multissítio (N domínios, 1 deploy) construída
como **8 células Django isoladas** (catalogo, funil, quiz, leads, checkout,
pagamentos, alunos, mensageria) que só se falam por HTTP versionado
(`contracts/*.openapi.yaml`) ou eventos (`contracts/eventos/*.v1.json`) — nunca
por import de código nem leitura de banco alheio. O motivo de existir: cobrar
via Pix/cartão (Mercado Pago) com o mínimo de invariantes de dinheiro
quebráveis, e um raio de explosão de qualquer falha = **1 célula**.

## 1. Mapa de documentos — o que ler, e quando

| Documento | Leia quando | O que resolve |
|---|---|---|
| **`ARMADILHAS.md`** | **Sempre, primeiro** — é curto: a regra de uso + a partida rápida (§2). | Manda você para o índice. Desde 23/08/2026 o conteúdo é **uma entrada por arquivo** em `armadilhas/`, não um monólito. |
| **`armadilhas/INDICE.md`** | **Sempre, junto com o de cima.** | Uma linha por armadilha, com a mensagem de erro crua. Ctrl+F pelo seu erro e **abra só a entrada que casar** — nunca a pasta inteira. |
| `ARMADILHAS-OPERACAO.md` | Maestro de lote, quem vai mergear, quem fala com o humano. | §1 o que só o mantenedor resolve · como se mergeia (§5.8–§5.9) · painéis (§7.1–§7.4) · §9 dívidas abertas. |
| `docs/historico/RESOLVIDAS.md` | Só quando precisar do histórico de um item já encerrado. | Armadilhas resolvidas — fora da dieta de um despacho normal. |
| `CLAUDE.md` | Sempre (Claude Code lê sozinho; outras ferramentas, leia à mão). | Instruções de operação específicas deste harness — painel obrigatório, etc. |
| `CONSTITUICAO.md` | Antes de qualquer código. | As leis que não se negociam (4 muralhas, escada da imposição). |
| `constituicoes/AGENTS.<celula>.md` | Antes de tocar UMA célula específica. | Jurisdição, fronteiras, o que a célula expõe/consome/emite. |
| `RITOS.md` | Antes de abrir uma sessão de trabalho. | Como nasce um worktree, a declaração obrigatória, catraca verde, mudança de contrato, emergência. |
| `INVARIANTES.md` | Antes de tocar dinheiro, webhook, matrícula ou multissítio. | INV-P1 a P11 + INV-CI01 (os portões da própria CI). |
| `CAMINHO-DOURADO.md` | Quando o despacho citar `RECEITAS: R_`. | As receitas canônicas — cole, não invente. |
| `ESQUELETO-QUE-ANDA.md` | Para entender o que "integração pronta" significa aqui. | A transação sandbox de ponta a ponta (Fase D). |
| `02-RED-TEAM.md` | Fase E (atual). | Os 15 golpes de graduação — o rito ainda não fechou. |
| `services/<celula>/LICOES.md` | Ao tocar UMA célula. | Decisões e armadilhas só daquela célula (se existir). |
| `RUNBOOK-FASE-D.md` | Ao rodar, depurar ou estender o esqueleto que anda. | Manual operacional do que a Fase D entregou (comandos, pendências herdadas). |
| **`docs/decisoes/RETROSPECTIVA-FASE-D.md`** | **Depois deste arquivo e do `armadilhas/INDICE.md`, antes de escrever código.** | Os **8 padrões que atravessam** as 67 armadilhas — o andar de cima do catálogo (falso-verde, garantia sem mecanismo, prova de fora, fail-closed na borda, humano no caminho crítico, contexto é orçamento, sessões paralelas, viabilidade sem ler config). Existe porque conhecer os casos não impede repetir a categoria. |
| `00-LEIA-PRIMEIRO.md`, `01-BRIEF-FASE-0.md`, `PROMPTS-INICIAIS.md` | Só para entender a HISTÓRIA (como o kit nasceu). | Framing original de bootstrapping — a Fase 0 já fechou; não descreve o estado atual. |
| `arquivos/*.html` | **Provavelmente você não consegue ler isto.** | Painéis para o humano (não-técnico). `arquivos/` está no `.gitignore` — não existe dentro de um worktree de célula. Se você é root window e consegue ver, é conveniência, nunca fonte de lei. |

**Ordem de leitura para uma sessão nova, root window, sem tarefa ainda definida:**
este arquivo → `ARMADILHAS.md` (§2 partida rápida) + `armadilhas/INDICE.md` →
`docs/decisoes/RETROSPECTIVA-FASE-D.md` (os 8 padrões — leitura curta, evita
repetir a CATEGORIA de erro que o catálogo já cobre caso a caso) →
`ARMADILHAS-OPERACAO.md` §1 → `CONSTITUICAO.md` → `RITOS.md` §1 →
pergunte ao humano qual é a tarefa, ou veja `git log`/`gh pr list` para inferir
onde o projeto parou.

## 2. Estado do projeto (fato registrado em 21/08/2026 — **verifique antes de confiar**)

```bash
git log --oneline -20
gh pr list --state all --limit 20
gh api repos/abundanciabr/sitesdoreino/branches/main/protection   # ver nota H3 abaixo
```

| Fase | O que é | Estado em 21/08/2026 |
|---|---|---|
| Fase 0 | Fundação (impossibilidades, jaula verde vazia, contratos congelados) | ✅ concluída, sobreviveu à auditoria |
| Fase B | As 8 células nascem vazias, CI verde antes de existir feature | ✅ concluída (8/8) |
| Fase D | O esqueleto que anda — 1 transação sandbox ponta a ponta | ✅ concluída localmente — 8/8 elos verdes (PRs #15 a #32). **2 de 4 critérios** de `ESQUELETO-QUE-ANDA.md`: ✅ 1 (local) · ✅ 3 (drill de rollback cronometrado, **76s**, 23/08/2026 — `RUNBOOK-FASE-D.md` §6) · ☐ 2 (VPS com cartão APRO + webhook real — **adiado por decisão do mantenedor**, exige obra de checkout + passo dele no painel do MP; mapa em §5.1–5.3) · ☐ 4 (fecha junto com o 2). |
| Fase E | Red-team — 15 golpes deliberados contra as muralhas | 🟡 **em andamento — 5 rodados, 4 ☑ na tabela.** Golpes 1–4 bloqueados e marcados (PRs #33, #36, #34, #37, fechados sem merge). O **golpe 5 rodou e bloqueou** (evidência `lint-imports` FAIL→PASS, commit `a05e085` na branch `redteam/golpe5-pix-importa-card`) mas **a linha dele em `02-RED-TEAM.md` ainda é ☐ e a branch nunca foi mergeada** — ver §2.1. **A tabela de `02-RED-TEAM.md` é a fonte de verdade do certificado; leia-a, não confie nesta linha.** |

### 2.1 Trabalho executado que não chegou à `main` — confira antes de refazer

Durante a Fase E, mais de uma sessão trabalha no repositório ao mesmo tempo
(`ARMADILHAS-OPERACAO.md` §7.1 e `armadilhas/` §7.6). Consequência observada em 21/08/2026: **o golpe
5 foi executado de verdade e bloqueou** — evidência crua de `lint-imports`
FAIL→PASS nos dois sentidos, e a confirmação escrita em
`services/pagamentos/LICOES.md` no commit `a05e085` — mas esse commit vive
**só** na branch `redteam/golpe5-pix-importa-card`, que nunca virou PR. A
linha 5 de `02-RED-TEAM.md` continua `☐` tanto na branch quanto na `main`.

Antes de assumir que um golpe (ou qualquer tarefa) "nunca foi feito" porque a
tabela diz `☐`, verifique se o trabalho existe numa branch não mergeada:

```bash
git fetch origin
git branch -r --no-merged origin/main        # branches com trabalho fora da main
git log --oneline origin/main..origin/<branch>
```

Isto vale como regra geral neste repositório: **a ausência de uma marcação não
prova a ausência do trabalho** — prova apenas que o certificado não foi
emitido. As duas coisas precisam ser fechadas, e confundi-las custa refazer
trabalho que já existe.

**Gap conhecido, aberto, BLOQUEADO (não é bug para "consertar", e não é escolha):**
não existe branch protection nativa do GitHub neste repositório —
`gh api .../branches/main/protection` responde `403 "Upgrade to GitHub Pro or
make this repository public"`.

> **Não recomende "assine o GitHub Pro".** Atualizado em 21/08/2026: o cartão do
> mantenedor **não é aceito pelo GitHub** e não há outra forma de pagamento —
> a porta está fechada por impossibilidade, não por decisão de custo. Quatro
> consultorias externas independentes recomendaram exatamente isso sem saber
> da restrição; o conselho é morto. As saídas vivas estão em
> `docs/decisoes/SINTESE-E-PLANO.md` §1 — a imediata é um **portão no workflow
> de deploy** (consultar `check-runs` do commit e abortar se não estiver verde:
> não protege a `main`, mas protege a VPS e o cliente, que é onde dói).

Consequências diretas para qualquer agente:

- Push direto na `main` **não é bloqueado pelo GitHub** — só por
  `.githooks/pre-push` (`core.hooksPath`), que vale só nesta máquina/clone.
- "Require review from Code Owners" **não está ativo** — `.github/CODEOWNERS`
  existe mas é só sugestão de revisor até essa opção ser ligada.
- A mitigação real hoje: `python ci/mergear.py <PR>` (recusa mergear PR com
  check vermelho, quando o merge sai do terminal) + workflow `alarme-main`
  (abre issue se a `main` quebrar DEPOIS do fato — alarme, não portão).
- **Nunca trate um merge ou um push como seguro só porque "o GitHub deixou"** —
  deixar passar é o comportamento esperado enquanto este item não for resolvido.
  Detalhe completo: `ARMADILHAS-OPERACAO.md` §1 item H3, `INVARIANTES.md` (seção
  "A cadeia de merge não está fechada").

**Atrito H6, resolvido em 22/08/2026:** `ci/mergear.py` não usa mais `--yes`
(o `gh` 2.97.0 desta máquina não tem a flag) e ganhou o caminho não-interativo
`--confirmo <N>`, com conferência `state=MERGED` embutida — o comando que o
script imprime voltou a ser o comando que funciona. E, desde a mesma data,
**mergear é trabalho do agente** (Lei 4; RITOS.md §2 peça 4):
`python ci/mergear.py <N> --confirmo <N>`, nunca o botão do site.

## 3. As 8 células

| Célula | Papel | Banco | Merge | Status (21/08/2026) |
|---|---|---|---|---|
| `catalogo` | Fonte de verdade de site/produto/oferta; resolve Host→Site (CONV-SITE) para as demais | `catalogo_db` | auto (CI verde) | ✅ Fase D — PR #15 |
| `checkout` | Sessão, snapshot imutável do pedido, order bumps, páginas de pagamento | `checkout_db` | agente — portão verde + anúncio (Lei 4) | ✅ Fase D — PR #17 + #24 |
| `pagamentos` | Intents Pix/cartão via Mercado Pago, webhooks, outbox de eventos de dinheiro | `pagamentos_db` | agente — portão verde + anúncio (Lei 4) | ✅ Fase D — PR #16 + #19 |
| `alunos` | Matrícula por evento (`pagamento.aprovado`), idempotente e sob lock | `alunos_db` | auto (CI verde) | ✅ Fase D — PR #26 + #27 + #32 |
| `leads` | Upsert de pessoa + timeline por evento | `leads_db` | auto (CI verde) | ✅ Fase D — PR #29 |
| `mensageria` | Envios (e-mail/WhatsApp) disparados por evento — provedores hoje são stubs que logam | `mensageria_db` (role `mensageria_user`) — log de envios e templates | auto (CI verde) | ✅ Fase D — PR #25 |
| `quiz` | Fluxo de perguntas, pontuação server-side, emite `quiz.completado.v1` | `quiz_db` | auto (CI verde) | ✅ Fase D — PR #28 (resolução de site LOCAL, decisão aceita — ver `services/quiz/LICOES.md`) |
| `funil` | Vitrine/landing mínima, stateless, preserva UTM até o checkout | sem banco (stateless) | auto (CI verde) | ✅ Fase D — PR #30 |

Nenhuma área tem merge humano desde 22/08/2026
(`docs/decisoes/DECISAO-merge-pelo-agente.md`): o agente mergeia tudo pelo portão
(`ci/mergear.py`), inclusive `contracts/`, `infra/`, `ci/`, `.github/` e os
arquivos de raiz que são lei (`CONSTITUICAO.md`, `INVARIANTES.md`, `RITOS.md`,
`CAMINHO-DOURADO.md`) — nesses caminhos CODEOWNERS, só com mandato do despacho e
com anúncio nominal no relatório (Lei 4). O `.github/CODEOWNERS` virou mapa de
jurisdição (diz onde o anúncio é obrigatório), não trava.

## 4. Como operar uma sessão (RITOS.md §1, resumo executável)

> **Vários despachos em paralelo?** A sessão-maestro (janela raiz) rege pelo
> `RUNBOOK-LOTES.md` — este §4 descreve UMA sessão de célula; o runbook descreve
> como N delas rodam juntas e como a janela de merge fecha o lote.

```bash
git fetch origin
git worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa> origin/main
cd ../wt-<celula>-<tarefa>/services/<celula>
make ci   # baseline PRECISA estar verde antes de tocar qualquer arquivo
```

**Primeira linha da primeira resposta do agente** (obrigatória):
> "Li `CONSTITUICAO.md` e `constituicoes/AGENTS.<celula>.md`. Worktree:
> `wt-<celula>-<tarefa>`. Branch: `agent/<celula>/<tarefa>`. `git status`:
> limpo. Baseline: `make ci` verde. Tarefa: [uma frase]."

Se o baseline não estiver verde: **pare e reporte** — consertar `main`
quebrada não é escopo de sessão de feature.

Regras de anti-thrashing que valem sempre (RITOS.md §2): commit a cada estado
verde (nunca `git add -A`); duas tentativas de correção falharam ⇒
`git reset --hard <último-verde>` e reporte — a terceira tentativa é onde
nascem labirintos; teste-guarda é intocável (nunca deletar/afrouxar para
passar — se parecer errado, PARE e reporte).

## 5. As leis que não se discute (CONSTITUICAO.md, resumo)

- **4 muralhas:** execução (1 processo/porta por célula), dados (1 database +
  1 role Postgres por célula — cruzar é `permission denied`, não "proibido"),
  código (1 sessão = 1 célula = 1 worktree), contrato (só HTTP versionado ou
  evento versionado entre células).
- **3 pecados:** importar código de outra célula; ler/escrever banco de outra
  célula; duplicar-e-divergir comportamento. Virtude: copiar dados (snapshot).
- **Escada da Imposição:** toda regra sobe de esperança → documento → processo
  → portão mecânico → impossibilidade física. Prosa nova numa constituição é
  dívida — abra `issue arquitetura:`/`mecanizar:`.
- **Lei das 2h da manhã:** emergência = rollback (RITOS.md §4), nunca hotfix
  no servidor. Agentes não têm chave SSH da VPS — inexistência, não proibição.
- **Evidência falsificável:** "eu arrumei" não é aceito. Todo trabalho em
  invariante mostra a saída crua do teste-guarda vermelho→verde.

## 6. Dinheiro tem lei própria — índice de `INVARIANTES.md`

| Código | Em 1 linha | Célula dona |
|---|---|---|
| INV-P1 | Snapshot do pedido é create-only | checkout |
| INV-P2 | Dinheiro é calculado no servidor, nunca confiado do payload | checkout |
| INV-P3 | Webhook idempotente por `mp_payment_id` | pagamentos |
| INV-P4 | Criação de intent idempotente por `X-Idempotency-Key` | pagamentos |
| INV-P5 | Matrícula sob lock, idempotente por `order_id` | alunos |
| INV-P6 | Outbox transacional (evento e estado nascem juntos ou nenhum nasce) | pagamentos |
| INV-P7 | Status na UI deriva SEMPRE de `GET` ao servidor | checkout |
| INV-P8 | Segredo de produção só existe na VPS — dev/CI só conhecem `TEST-` | plataforma |
| INV-P9 | Pix e cartão mutuamente invisíveis (nem import, nem estado) | pagamentos |
| INV-P10 | Webhook sem assinatura válida ⇒ 403, zero efeito | pagamentos |
| INV-P11 | Fronteira de site — host desconhecido é 404, nunca site padrão | catalogo + checkout |
| INV-CI01 | Portão crítico é fail-closed — 4 estados (PASS/FAIL/ERROR/SKIP), nunca 2 | `ci/` (repositório) |

## 7. Receitas — não invente o caminho feliz (`CAMINHO-DOURADO.md`, índice)

| Preciso de... | Receita |
|---|---|
| Expor endpoint novo | R1 |
| Chamar API de outra célula | R2 |
| Avisar a plataforma que algo aconteceu | R3 |
| Reagir a evento de fora da célula | R4 |
| Proteger uma regra que não pode quebrar | R5 |
| Criar página nova | R6 |
| Mudar schema do banco (expand-and-contract) | R7 |
| Task assíncrona interna | R8 |
| Seed/fixture idempotente | R9 |
| Marker de smoke test | R10 |
| Site/domínio novo no ar | R11 |

O despacho cita a receita por número; carregue no contexto só a(s) citada(s) —
nunca `CAMINHO-DOURADO.md` inteiro (dieta de contexto, RITOS.md §1).

## 8. Portões de CI — dois `make ci` diferentes, não confunda

Existe um `make ci` na RAIZ e outro DENTRO de `services/<celula>/` — mesmo
nome, escopos diferentes. Rodar um no lugar do outro dá falso sinal de
"pronto":

| Comando | Onde roda | O que verifica |
|---|---|---|
| `python ci/doctor.py` (raiz) | raiz do repo | "este ambiente consegue executar o trabalho?" (read-only, diagnóstico) |
| `make ci` == `python ci/ci.py` (raiz) | raiz do repo | portões de REPOSITÓRIO: cerca de célula, orçamento de arquivos, guarda de segredos, freeze de contrato de TODAS as células |
| `make ci` (dentro de `services/<celula>/`) | dentro da célula | a Definição de Pronto DA CÉLULA: `lint` (black + lint-imports) + `type` (mypy) + `test` (pytest) + `contrato-check` (só desta célula) — **é este que RITOS.md §1 manda rodar como baseline** |
| `make celula CELULA=<x>` (raiz) | raiz | os dois combinados: portões de repositório + `make ci` da célula `<x>` |
| `make esqueleto` (raiz) | raiz | `bash e2e/esqueleto.sh` — a transação de ponta a ponta (ver `RUNBOOK-FASE-D.md`) |
| `make mergear PR=<n>` / `python ci/mergear.py <n>` (raiz) | raiz | confere checks reais do PR no GitHub e recusa mergear se algo não estiver verde |

| Estado | Significa | Exit |
|---|---|---|
| `PASS` | mediu e está correto | 0 |
| `FAIL` | mediu e achou violação — conserte o **código** | 1 |
| `ERROR` | **não conseguiu medir** — conserte o **ambiente** | 2 |
| `SKIP` | declarado não aplicável, com motivo escrito | 0 |

`ERROR` nunca é "quase passou". Ausência de evidência nunca é evidência de
sucesso (INV-CI01) — se um portão disser "OK" sem ter medido nada, isso é o
próprio bug que `ci/contract_freeze.py` foi reescrito para eliminar
(`ARMADILHAS.md` §5.6/§5.7).

## 9. Antes de abrir a boca — checklist dos primeiros 5 minutos

1. Este arquivo, inteiro.
2. `ARMADILHAS.md` §2 (partida rápida) + `armadilhas/INDICE.md` (o mapa das
   armadilhas — abra só o que casar); `ARMADILHAS-OPERACAO.md` §1 se for maestro
   de lote ou for mergear (o que só o humano resolve).
3. Se a tarefa já é conhecida: `constituicoes/AGENTS.<celula>.md` +
   `services/<celula>/LICOES.md` (se existir).
4. Rode o baseline (`make ci`) ANTES de tocar qualquer arquivo. Vermelho ⇒
   pare e reporte.
5. Se não há tarefa definida ainda: rode os comandos da §2 acima para saber
   de fato onde o projeto parou, e pergunte ao humano em vez de assumir.

## 10. Ao terminar uma tarefa

- Handoff completo no corpo do PR (RITOS.md §1): branch, arquivos tocados,
  resultado de `make ci`, pendências, riscos.
- Acrescente o que aprendeu: transversal (qualquer célula) vai em
  `ARMADILHAS.md`; específico da célula vai em `services/<celula>/LICOES.md`.
  Não crie seção nova se já existir uma que sirva.
- Se a correção definitiva não estava nas suas mãos (precisa de instalação,
  plano pago, decisão de arquitetura): registre na tabela `§1` de
  `ARMADILHAS.md` **e diga isso no relatório final em texto claro** — contornar
  em silêncio faz o mesmo atrito voltar no próximo despacho.
- **Acrescente um registro ao livro de ocorrências** — arquivo novo em
  `painel/registros/` (molde em `painel/LEIA-ME.md`), depois
  `node painel/gerar_manifesto.js`. **Mudou em 26/08/2026:** o livro é
  versionado, então ele EXISTE dentro do seu worktree e o gesto é seu, em
  qualquer sessão — não mais "só da janela raiz". Registro é sempre arquivo
  NOVO, nunca edição de um existente (é o que faz sessões paralelas pararem de
  colidir, igual às armadilhas); atualização ou resposta a um pedido é outro
  registro, com `responde_a`. A `muralha-do-painel` reprova o PR se o
  manifesto ficar para trás. Os painéis antigos de `arquivos/` são lápides —
  não os edite. Ver `CLAUDE.md`.

## 11. O que este documento NÃO substitui

Isto é um MAPA, não o território. Antes de decidir qualquer coisa que toque:
dinheiro/webhook/matrícula/multissítio → leia `INVARIANTES.md` de verdade;
uma célula específica → leia a constituição dela inteira, não só a linha da
tabela da §3; uma receita citada no despacho → leia a receita completa em
`CAMINHO-DOURADO.md`, não confie no resumo de 1 linha da §7. Este arquivo
existe para você não perder 10 minutos descobrindo QUAL documento ler — não
para substituir a leitura dele.
