publico-para-ia: true

# PLANO — a orquestração autônoma dos robôs (as fichas, o despachante que não dorme e o que ele nunca decide)

> **Estado: PROPOSTO em 05/09/2026, esperando a decisão do mantenedor**
> (registro `20260905-005` no livro, PR #PR_NUMERO). Em 04/09/2026 ele perguntou
> "como criar um sistema de agentes e sub-agentes de IA para gerenciar os robôs,
> de modo que trabalhem com mais agilidade e velocidade", e escolheu, em pergunta
> estruturada, receber o plano completo como documento antes de qualquer código.
> Nenhuma tarefa da escada nasceu na fila: elas nascem quando ele aprovar (§11).

**Escrito em 05/09/2026**, a partir de: a pergunta dele; a medição da fila, do
runbook de lotes e da pista contra o `origin/main` (commit `540f6994`); o veredito
da central de orquestração (`docs/consultorias/central-de-orquestracao/VEREDITO.md`),
que em 29/08/2026 já tinha adiado o despachante como evolução ("hoje quem despacha
é o mantenedor com a maestro"); e a documentação oficial do Claude Code lida nesse
dia (sub-agentes, GitHub Actions, modo programático, rotinas na nuvem e times de
agentes). Molde: `PLANO-CELULA-CURSOS.md` (a escada e o critério de morte) e
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` (o registro auditável de cada recomendação).

Este documento NÃO é um painel: não guarda estado e não se atualiza sozinho. Quem
responde "isto foi feito?" é o livro (`painel/registros/`) e a fila (`fila/`).

---

## §1 A pergunta, e a resposta em uma frase

A pergunta: como montar agentes e sub-agentes de IA para os robôs desta casa
trabalharem com mais agilidade e velocidade?

A resposta: **a hierarquia já existe. O que falta é um robô que despache trabalho
sem esperar o mantenedor abrir uma janela, e fichas fixas para cada tipo de robô
nascer pronto.** Velocidade de robô não é o gargalo desta casa. O gargalo é o tempo
em que nenhum robô está acordado.

## §2 O que a casa já tem, medido

| Papel | Quem faz hoje | Onde está escrito | Acorda sozinho? |
|---|---|---|---|
| O agente que rege | a sessão-maestro, no PC do mantenedor | `RUNBOOK-LOTES.md` | não: só quando ele digita "toque um lote" |
| Os sub-agentes que constroem | os despachos, um por bancada, um por célula | `CAMINHO-DOURADO.md` §2 (o brief), `RITOS.md` §1 e §5 | não: a maestro dispara cada um |
| O balcão (quem está com o quê) | `fila/` + `ci/fila.py`, com trava atômica no servidor do GitHub | `fila/LEIA-ME.md` | sim: a trava é do servidor |
| A pista (quem mergeia) | `.github/workflows/pouso.yml` | `RITOS.md` §2 peça 5 | sim: agendada, um PR por vez |
| Os portões (quem julga) | muralhas, `ci-celula`, portão de deploy, vacina do deploy, alarme da main | `ci/`, `.github/workflows/` | sim |
| O livro (a memória) | `painel/registros/` | `painel/LEIA-ME.md` | não: robô escreve, humano lê |

Ou seja: a casa já é um sistema de agentes e sub-agentes. A maestro é o agente, os
despachos são os sub-agentes, a pista e os portões são robôs de máquina. A prova de
que um robô sem ninguém na frente do computador funciona nesta casa é a própria
pista: desde 29/08/2026 ela mergeia sozinha, dezenas de vezes por dia.

Os números da fila em 05/09/2026, calculados pelo balcão
(`python ci/fila.py listar --json`, no commit `540f6994`):

| Medição | Valor |
|---|---|
| Tarefas registradas | 128 |
| Concluídas | 97 |
| Na fila: despacho pronto, dependências satisfeitas, ninguém pegou | 11 |
| Esperando só outra tarefa da fila (destravam sozinhas quando ela fecha) | 10 |
| Trancadas por estarem desatualizadas (substitutas já criadas) | 8 |
| Esperando uma prova que só o mantenedor pode dar | 1 |
| Reivindicada sem desfecho | 1 |
| Abertas SEM despacho pronto | 0 |

As 11 não esperam por decisão nenhuma, e as 10 atrás delas também não. Esperam
por um robô. Uma única tarefa espera por ele.

## §3 Onde o tempo se perde (as três causas, e o que não é causa)

1. **Entre uma sessão dele e a próxima, nada anda.** Toda tarefa da fila já carrega
   o despacho pronto, e mesmo assim 11 delas ficam paradas horas ou dias (com 10
   atrás, esperando só por elas), porque o único gatilho que existe é ele abrir
   uma janela e digitar. A consultoria de
   29/08/2026 viu isso e adiou de propósito: "Scheduler / melhor próxima tarefa:
   hoje quem despacha é o mantenedor com a maestro" (VEREDITO, tabela de evolução).
   Este plano é essa evolução.

2. **Cada despacho nasce do zero.** A maestro redige o rito inteiro dentro de cada
   brief, à mão, toda vez: bancada, balcão, orçamento, registro, pouso, mutação. O
   papel fixo de "construtor", "revisor" e "escrivão" não existe como ficha
   reutilizável, e por isso cada lote paga de novo o custo de ensiná-lo. Contexto é
   orçamento (`RETROSPECTIVA-FASE-D.md`, padrão 6).

3. **Uma cabeça só carrega o lote.** Cinco despachos devolvem cinco relatórios
   para o mesmo contexto da maestro, que também compõe, vigia, mede o que os
   despachos reportam (RUNBOOK §9, Lote A, lição 2) e escreve o fechamento. O
   contexto enche, e a maestro fica mais lenta e menos precisa no fim do lote.

O que NÃO é causa, e portanto não é onde se mexe: o pipeline (mediana de 8,4
minutos entre o PR aberto e o merge, medida em 31/08/2026, `armadilhas/258`); a
pista serial (é serial de propósito, `armadilhas/156`); a velocidade com que um
robô escreve código. E existe uma fila que nenhum robô encurta: a caixa "Precisa de você" do
painel, feita das decisões que só ele toma. Robô a mais não a esvazia. Enche mais
rápido.

## §4 O vocabulário, traduzido para a casa

O Claude Code oferece seis peças. Cada uma ganha aqui um nome de casa e um veredito.

| Peça oficial | Nome na casa | O que é | Serve para |
|---|---|---|---|
| Sub-agente com definição em `.claude/agents/<nome>.md` | **ficha de robô** | arquivo versionado com `name`, `description`, `tools`, `model`, `effort`, `maxTurns`, `memory` e o texto fixo do papel; o harness delega por ele, e ele pode ser chamado pelo nome | o degrau 1 |
| Modo programático (`claude -p`) | **robô sem janela** | roda um prompt até o fim sem ninguém na frente; `--permission-prompts none` tira a caixa de pergunta, `--max-turns` limita o trabalho, `--output-format json` devolve custo e resultado | o motor do degrau 2 |
| Claude Code GitHub Action (`anthropics/claude-code-action@v1`) | **robô no runner** | o mesmo Claude Code rodando dentro de um workflow do GitHub, com `prompt`, `claude_args`, e autenticado pela assinatura (`claude_code_oauth_token`, gerado por `claude setup-token`) ou por chave (`anthropic_api_key`); minutos de runner grátis em repositório público | o degrau 2 |
| Rotina na nuvem (`/schedule`, `claude.ai/code/routines`) | **robô hospedado pela Anthropic** | prompt salvo que roda na infraestrutura da Anthropic num horário (mínimo 1 h), na assinatura, com teto diário de execuções e sem pedido de permissão; os commits saem em nome do dono da conta, em ramos `claude/` | o degrau 3, e só como reserva |
| Time de agentes (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) | **time presencial** | colegas com contexto próprio que se falam por caixa de mensagens e dividem uma lista de tarefas; experimental, e só em sessão interativa (não roda em `-p`) | a maestro no PC, quando ele está presente; fora da escada |
| Agent SDK (Python/TypeScript) | **a biblioteca por trás** | o que o `-p` e a Action usam; só entra se um dia o despachante precisar de lógica que YAML e Python de `ci/` não expressem | nada, por agora |

Os hooks (`.claude/settings.json`) já são as muralhas da casa, e continuam como estão.

## §5 A escada

Cada degrau diz o que é, o que muda para o mantenedor, o que precisa existir, o
que NÃO faz, e qual evidência o declara pronto. A ordem é obrigatória: o degrau 2
roda a ficha do degrau 1.

### Degrau 1: as fichas de robô (`.claude/agents/`)

**O que é.** Três arquivos versionados, um por papel, com o rito fixo da casa
escrito uma vez só:

- **`despacho.md`, o construtor.** Carrega o que hoje a maestro cola em todo brief:
  a bancada primeiro (`RITOS.md` §1), o balcão de dentro dela (§5), o orçamento de
  15 arquivos, a suíte da célula como primeiro gesto (RUNBOOK §9, lição 3 do lote
  de 04/09), o registro que embarca no PR citando o número (`armadilhas/185` e
  `248`), o pouso pedido por `python ci/esperar.py --checks N --teto 20 --e-pousar`,
  a prova de cada guarda por mutação depois do verde, e as duas frases que
  autorizam a parar: *"se a tela precisar de algo que só outra célula pode dar,
  PARE e reporte em vez de atravessar a cerca"* e *"decisão que é do mantenedor
  vira evento `bloqueada` mais registro com `precisa_do_dono: true`, nunca
  pergunta"*. A ficha não usa o `isolation: worktree` do harness: a bancada nasce
  pelo rito, com o nome `wt-<area>-<tarefa>` e o ramo `agent/<area>/<tarefa>` que
  a pista e a fila esperam (RUNBOOK §4).
- **`revisor.md`, o crítico.** Só lê (`Read`, `Grep`, `Glob`, e `Bash` restrito a
  `git diff` e à suíte). Lê o PR como o revisor mais implacável (Padrão de
  Trabalho, regra 8), prova cada guarda por mutação e devolve a lista do que
  reprovaria. Não edita nada. Modelo forte, esforço alto.
- **`escrivao.md`, o escrivão.** Escreve o registro do livro pelo molde
  (`painel/LEIA-ME.md`), com menos de 1 KB e citando o número do PR; o evento da
  fila; a armadilha com número pedido ao almoxarife; e regenera o índice. Modelo
  mais barato, esforço baixo, ferramentas de escrita restritas a `painel/registros/`,
  `fila/eventos/` e `armadilhas/`. Existe porque o registro é o passo que mais se
  esquece: em 31/08/2026, 12 das 25 aterrissagens de um dia eram PRs pagando
  dívida atrasada (`armadilhas/248`).

**O que muda para o mantenedor.** Nada visível. O lote seguinte gasta menos
contexto por despacho, porque o brief passa a carregar só a tarefa e as
armadilhas dela, e o rito vem da ficha.

**O que precisa existir.** Um PR: três arquivos em `.claude/agents/` e um
teste-guarda em `ci/tests/test_fichas_de_robo.py` (frontmatter válido, `name`
igual ao nome do arquivo, só campos que o Claude Code conhece, `tools` do revisor
sem ferramenta de escrita). `ci/` é caminho CODEOWNERS: o mandato é a aprovação
deste plano.

**O que NÃO faz.** Não muda nenhum rito. Não despacha nada sozinho.

**Evidência de pronto.** Um despacho real disparado pela ficha `despacho`, com PR
pousado pela pista, e o brief dele sem uma linha de rito.

### Degrau 2: o despachante (o robô que não dorme)

**O que é.** Um workflow do GitHub, irmão da pista, que acorda sozinho, pega a
próxima tarefa disponível da fila e roda o Claude Code dentro do runner para
construí-la de ponta a ponta. O mantenedor acorda com PRs abertos (em sombra) ou
pousados (depois da graduação).

**O desenho, peça por peça.**

1. **A lógica mora em Python, o YAML é fino.** `ci/despachante.py` decide
   (interruptor, teto, escolha da tarefa, bancada, trava), com testes em
   `ci/tests/test_despachante.py`. O workflow `.github/workflows/despachante.yml`
   só encadeia os passos, como `mergear.py` e `esperar.py` já fazem com a pista.
2. **Gatilhos.** `schedule` a cada 2 horas, e `workflow_dispatch` (o botão, com o
   `TAR-NNN` opcional para escolher a tarefa). `concurrency: despachante`: um por
   vez. `timeout-minutes: 45`. Duas regras do GitHub que valem aqui: o agendamento
   roda sempre da definição da `main` (o mesmo juiz da pista, decisão 2 do
   `pouso.yml`), e em repositório público ele se desliga depois de 60 dias sem
   atividade.
3. **O interruptor, fail-closed.** Variável de repositório `DESPACHANTE` com três
   valores: `desligado`, `sombra`, `ligado`. Ausente é `desligado`: o robô sai em
   verde dizendo por quê. Mesmo desenho do interruptor da economia da gamificação.
4. **O teto do dia, calculado da fila.** O despachante conta os eventos
   `reivindicada` do dia com `quem: despachante-*` em `fila/eventos/`. Chegou ao
   teto, sai em verde dizendo "teto do dia". Nenhum contador paralelo: o estado é
   calculado, como tudo na fila.
5. **A escolha da tarefa.** `python ci/fila.py listar --ao-vivo --json`, filtra
   "na fila", exclui `toca` com caminho CODEOWNERS (`contracts/`, `infra/`, `ci/`,
   `.github/`, `pagamentos`, `checkout`; essas ficam para a maestro com mandato) e
   pega a mais antiga. O degrau 4 troca "mais antiga" por "a que mais move o
   negócio".
6. **A bancada nasce DENTRO do runner, e isso não é opcional.** O checkout do
   runner tem `.git` como diretório, e é exatamente assim que
   `ci/muralha_pasta_compartilhada.py` reconhece "clone principal" e recusa toda
   edição (`raiz_do_checkout`: `.git` diretório é espelho, `.git` arquivo é
   bancada). Os hooks de `.claude/settings.json` rodam no `-p` sem `--bare`.
   Então o despachante faz o rito de qualquer robô: `git worktree add
   ../wt-<area>-TAR-NNN -b agent/<area>/TAR-NNN`, e o Claude Code roda lá dentro.
   Medido em 05/09/2026 lendo o código da muralha; o canário confirma ao vivo.
7. **A trava.** `python ci/fila.py pegar TAR-NNN --quem despachante-<run_id>`, de
   dentro da bancada (`armadilhas/192`). Recusa do servidor significa que outro
   robô (uma sessão dele, ou uma maestro) pegou antes: sai em verde.
8. **O robô.** `anthropics/claude-code-action@v1` com `prompt` = o preâmbulo do
   despachante (o número da tarefa, o valor do interruptor, o `run_id`) mais o
   campo `despacho` da tarefa, tal qual está na fila; `claude_args` com `--agent
   despacho` (a ficha do degrau 1 vira a sessão inteira), `--max-turns`,
   `--permission-mode acceptEdits` e `--permission-prompts none` (a caixa de
   pergunta some, e a ficha já manda bloquear e registrar em vez de perguntar).
   Os serviços `postgres` e `redis` sobem como no `ci-celula.yml`, então a suíte
   da célula roda de verdade, no runner, antes de o PR existir.
9. **A entrega.** O robô faz o rito inteiro: constrói, roda a suíte, abre o PR
   pelo `gh`, escreve o registro citando o número, grava os eventos da fila, e:
   em `sombra`, comenta no PR *"aberto pelo despachante em sombra, run <id>"* e
   **não pede pouso**; em `ligado`, pede pouso com `esperar.py --checks N --teto
   20 --e-pousar`, e a pista mergeia como mergeia qualquer PR.
10. **A autenticação.** Pela assinatura (`claude_code_oauth_token`, segredo
    `CLAUDE_CODE_OAUTH_TOKEN` gerado por `claude setup-token` no PC dele) ou por
    chave (`anthropic_api_key`). É a decisão 2 do §8. O Claude GitHub App precisa
    estar instalado no repositório (só ele instala; é administrador), e os pushes
    do App disparam o CI, o que um push com o `GITHUB_TOKEN` padrão não faria
    (decisão 1 do `pouso.yml`, o mesmo motivo). O agendamento é atribuído pelo
    GitHub a quem editou a linha do `cron` por último, e essa pessoa tem de ser
    humana, senão a Action recusa o gatilho.

**Nascimento em sombra e graduação** (lei do Sistema Imunológico: regra nova
nasce em sombra dizendo o que teria feito).

- **Fase A, `sombra`.** Uma tarefa por passagem, teto de 6 por dia. O canário é
  uma tarefa de escrituração (documento, registro, armadilha), a mais inofensiva
  da fila, disparada pelo **botão** `workflow_dispatch`, apertado de verdade
  (`armadilhas/260`), e pela MESMA automação que vai rodar sozinha depois (RUNBOOK
  §9, lote da fila do painel, lição 1). O robô abre o PR e para. A maestro (ou
  ele) lê, e pede pouso à mão.
- **Graduação para `ligado`.** Depois de 5 PRs do despachante pousados pela pista
  sem devolução e sem revert, registrados no livro. A partir daí o robô pede
  pouso sozinho e o teto sobe para 12 por dia. Não graduar em 30 dias é o
  critério de morte (§9): sombra que não gradua é botão que ninguém aperta.

**O que o despachante NÃO faz, por desenho.**

- Não conduz Rito de Contrato (`RITOS.md` §3): tarefa que precisa de contrato fica
  `bloqueada` com o motivo, e a caixa "Precisa de você" a mostra.
- Não toca caminho CODEOWNERS (a escolha da tarefa já os exclui, e a cerca do CI
  reprovaria de qualquer forma).
- Não pergunta nada a ninguém: sem `AskUserQuestion`, a ficha manda bloquear e
  registrar com `precisa_do_dono: true`. A pergunta ao mantenedor continua sendo
  só da maestro (CLAUDE.md, seção "Como trabalhar com o mantenedor").
- Não mergeia: a pista é a única porta, e continua sendo.
- Não decide o que construir: só executa despachos que já estão na fila, escritos
  por uma sessão com contexto ou aprovados por ele.

**Custos.** Minutos de runner: grátis, repositório público (PLANO-MESTRE, Parte 1).
Tokens: a assinatura (a mesma franquia que os lotes já gastam; muda o horário, não
o total) ou a chave (paga por uso, sem teto próprio). Guardas de custo: `--max-turns`,
`timeout-minutes`, `concurrency` de um, e o teto do dia calculado da fila.

**O que precisa existir.** Dois PRs, ambos em caminho CODEOWNERS (`ci/`,
`.github/`), com o mandato deste plano: (A) `ci/despachante.py` + testes, provando
o interruptor fail-closed, o teto, a exclusão de CODEOWNERS e a escolha; (B) o
workflow, o preâmbulo do prompt e a linha em `painel/mapa-do-site.json` se o
mapa listar workflows. Mais o degrau 1 antes dos dois.

**Evidência de pronto.** Um run em `sombra` que abre PR real de uma tarefa da
fila, a suíte verde dentro do runner, o PR pousado depois pela pista, e um
registro no livro com o `run_id` e o número do PR. O veredito vem de `gh run
view <id> --json status,conclusion` e do estado do PR, nunca do verde do run: um
run verde diz que o robô terminou, não que a tarefa ficou pronta (a documentação
das rotinas diz isso com todas as letras, e a casa aprendeu do jeito caro em
`armadilhas/127`).

### Degrau 3: a rotina na nuvem (a alternativa medida, e por que fica de reserva)

**O que é.** O mesmo despachante, hospedado na infraestrutura da Anthropic em vez
do runner do GitHub: um prompt salvo em `claude.ai/code/routines` (ou por
`/schedule`), agendado, que clona o repositório e trabalha sem ninguém.

**O que a documentação garante.** Roda na assinatura (Pro, Max, Team, Enterprise),
com teto diário de execuções por conta e intervalo mínimo de 1 hora. Sem pedido de
permissão durante a execução. Rede em lista de permissões (registries e domínios
comuns de desenvolvimento; o resto exige configurar o ambiente). O ambiente aceita
um script de instalação com resultado em cache. Os commits e PRs saem **em nome do
dono da conta**, em ramos com prefixo `claude/`. O verde da execução significa que
a sessão terminou sem erro de infraestrutura, não que a tarefa deu certo.

**Por que o Actions vence, nesta casa.** (1) A pista, os portões e o CI já moram no
GitHub, e o juiz é a definição da `main`. (2) Os serviços `postgres` e `redis` já
existem como `services:` do CI; na nuvem eles teriam de ser instalados dentro do
sandbox pelo script de instalação, o que ninguém mediu. (3) O ramo e o autor do
trabalho são do robô (`agent/<area>/TAR-NNN`, `despachante-<run_id>`), não do
mantenedor: o livro e a fila continuam sabendo quem fez o quê. (4) O log do run
fica no repositório, auditável por qualquer sessão com `gh`.

**Quando a rotina entra.** Como reserva, se a assinatura não puder ser usada no
Actions (o token de `claude setup-token` for vetado ou parar de funcionar): a
rotina roda na assinatura com certeza, e a documentação diz isso. Nesse caso o
`ci/despachante.py` é o mesmo; muda só quem o chama.

### Degrau 4: o despachante que escolhe pelo dinheiro, e as ondas

Só depois de o degrau 2 estar `ligado` e provado.

- **A escolha por `move`.** Desde 04/09/2026 toda tarefa declara que resultado do
  placar ela move (`fila/LEIA-ME.md`, campo `move`). A regra 1 do RUNBOOK §3
  ("ordene pelo dinheiro") vira código em `ci/despachante.py escolher`: primeiro
  o cartão que o placar aponta como o mais atrasado, depois `depende_de`, depois
  a idade. Com teste.
- **O despacho recompilado do estado real** (VEREDITO, tabela de evolução). Antes
  de rodar, o despachante injeta no prompt as armadilhas do `toca` daquela tarefa
  (de `armadilhas/SINAIS.json` e `GUARDAS.json`), o `LICOES.md` da célula, e o
  pré-voo que a maestro faz à mão (RUNBOOK §2.4): `main` verde, deploy verde,
  nenhuma issue `main-vermelha` aberta. Pré-voo vermelho, o robô não despacha e
  registra.
- **As ondas.** N despachantes em paralelo com `toca` disjunto, um grupo de
  `concurrency` por célula. A trava da fila já impede dois robôs na mesma tarefa;
  a cerca de célula já impede dois PRs na mesma célula; a pista já serializa os
  merges. O que falta é só o teto de ondas, calculado como o teto do dia.

## §6 O que NÃO muda

Nenhuma lei da casa é emendada por este plano. Em particular:

- A pista continua a única porta de merge (Lei 4 com a emenda de 29/08/2026).
- O registro continua embarcando no PR, citando o próprio número (31/08/2026).
- A fila continua a única casa do "o que está por fazer", e o livro a única casa
  do "o que aconteceu". O despachante lê da fila e escreve no livro; não mantém
  lista própria (lei anti-duplicação).
- A trava da fila continua no servidor, e a bancada continua nascendo antes do
  balcão (`armadilhas/192`).
- O Rito de Contrato continua humano. Caminho CODEOWNERS continua exigindo mandato.
- O orçamento de 15 arquivos, a cerca de célula, a evidência vermelho→verde, a
  prova por mutação, e a lei do travessão nos textos publicados continuam iguais.
- Quem fala com o mantenedor continua sendo a maestro, por pergunta estruturada.
  O despachante nunca fala com ele: registra.

## §7 Riscos e guardas

| Risco | O que aconteceria | Guarda |
|---|---|---|
| Gasto sem teto (robô rodando a madrugada inteira) | franquia esgotada de manhã, ou conta de API surpresa | interruptor fail-closed; teto do dia calculado da fila; `--max-turns`; `timeout-minutes`; `concurrency` de um |
| Robô decidindo o que é do mantenedor | tela ou regra publicada sem ninguém ter escolhido | sem `AskUserQuestion`; a ficha manda `bloqueada` + `precisa_do_dono: true`; a escolha exclui CODEOWNERS; contrato só por Rito |
| Hooks do PC rodando no runner | a muralha da pasta recusaria toda edição, e o robô terminaria "verde" sem fazer nada | a bancada nasce dentro do runner (peça 6); o canário mede |
| Falso-verde do run | run verde com PR errado, ou sem PR | o veredito vem do PR e da pista; o registro cita `run_id` e PR; sombra antes de ligado |
| Robô acionando robô em laço | despachante reagindo a evento de PR que ele mesmo criou | o despachante não reage a evento de PR, só a horário e botão; a Action rejeita ator-robô por padrão |
| Segredo em repositório público | token exposto | segredo do GitHub, nunca em arquivo; o GitHub não entrega segredos a PR vindo de fork |
| Dois robôs na mesma tarefa | trabalho duplicado, PRs que se superam (`armadilhas/305`) | a trava do servidor (`fila.py pegar`); recusa é saída em verde |
| Armadilhas duplicadas por robôs em paralelo | o mesmo defeito catalogado três vezes (RUNBOOK §9, lição 2 do lote da fila) | um despachante por vez na fase A; ondas só no degrau 4 |
| Sombra eterna | o robô abre PRs que ninguém lê, e o desenho apodrece (`armadilhas/260`) | graduação em 5 pousos; morte em 30 dias sem graduar (§9) |
| A `main` quebrada de madrugada | o robô construiria em cima de vermelho | pré-voo do degrau 4 (até lá, a suíte da célula como primeiro gesto, que a ficha já exige) |

## §8 As decisões do mantenedor

Quatro decisões, todas dele, e o que acontece se ficarem paradas: as 11 tarefas
prontas (e as 10 atrás delas) continuam paradas entre as sessões dele. Nada
quebra. Nada acelera.

1. **A escada.** Aprovar como está, ou mudar a ordem. **Recomendação:** aprovar;
   os degraus 1 e 2 nascem no mesmo lote, porque o 2 roda a ficha do 1.
2. **Como o robô noturno é pago.** Pela assinatura (o token de `claude setup-token`
   vira o segredo `CLAUDE_CODE_OAUTH_TOKEN`; os runs gastam a franquia, sem
   cobrança à parte) ou por chave de API (cobrança por uso, sem teto próprio).
   **Recomendação:** assinatura. É a mesma franquia que os lotes já gastam, só que
   em outro horário, e não existe conta surpresa. A chave entra só se a franquia
   deixar de bastar, e aí é decisão nova.
3. **A confiança.** Quantos PRs em sombra antes de o robô pousar sozinho.
   **Recomendação:** 5 pousados pela pista sem devolução.
4. **O teto do dia.** **Recomendação:** 6 em sombra, 12 em ligado.

**O que só ele pode fazer**, e que chega como UM bloco de colar, com a janela
rotulada, no PR do degrau 2 (não agora): instalar o Claude GitHub App no
repositório; rodar `claude setup-token` no PC e colar o resultado como segredo
`CLAUDE_CODE_OAUTH_TOKEN`; criar a variável `DESPACHANTE` com o valor `sombra`;
e ser ele quem edita a linha do `cron`, para o agendamento ficar atribuído a uma
pessoa.

## §9 Critério de morte

O despachante é desligado (`DESPACHANTE=desligado`, com registro no livro) se, em
30 dias contados do primeiro run em sombra, qualquer uma destas for verdade:

- ele não graduou (menos de 5 PRs pousados sem devolução);
- os PRs dele devolvidos ou fechados como superados passaram dos pousados;
- o tempo de fila (tarefa criada até PR aberto) não caiu, medido pelos eventos;
- PRs dele ficaram 7 dias em sombra sem ninguém pedir pouso: sinal de que ninguém
  os lê, e robô que ninguém lê é `armadilhas/260`.

Desligar não apaga nada: o workflow fica, o interruptor fecha, e o que foi
aprendido vai para o `RUNBOOK-LOTES.md` §9 como lição de regência.

## §10 Armadilhas já mapeadas deste caminho

| # | O que ensina a este plano |
|---|---|
| 127 | deploy vermelho com a VPS viva: veredito de run se lê pela API, nunca pelo verde da lista |
| 135 | duas sessões na mesma pasta apagam o trabalho uma da outra; a bancada é lei, também no runner |
| 156 | a corrida contra a `main` não se vence sendo mais rápido: pede-se pouso e vai-se embora |
| 161 | espera sem teto parece trabalho; toda espera tem voz e tem teto |
| 185 | registro sem o número do PR é dívida real |
| 192 | pegar a tarefa antes da bancada deixa o comprovante órfão |
| 248 | a fila trava para todos e os robôs pagam a mesma dívida em paralelo |
| 251 | a pista reiniciava o PR mais antigo a cada passagem |
| 260 | o botão entregue, verde, e nunca apertado |
| 305 | resgatar PR antigo começa medindo se a `main` já o superou |
| 308 | o pouso automático morre no instante em que o verde chega (`mergeable` em recálculo) |
| 323 | a suíte de uma célula fica vermelha sozinha; o primeiro gesto de todo degrau é rodá-la |

## §11 O que fica decidido para o próximo agente

- **Ao aprovar, criar na fila, nesta ordem e com `--depende-de`:** a tarefa do
  degrau 1 (`toca: .claude ci`); a do núcleo do despachante (`toca: ci`); a do
  workflow (`toca: .github painel`); e a do canário em sombra (`toca: fila painel`),
  que é a que aperta o botão. O degrau 4 só nasce na fila depois da graduação.
- **Nomes fixos:** `.claude/agents/despacho.md`, `revisor.md`, `escrivao.md`;
  `ci/despachante.py` e `ci/tests/test_despachante.py`;
  `.github/workflows/despachante.yml`; a variável `DESPACHANTE`; o `--quem
  despachante-<run_id>`; o segredo `CLAUDE_CODE_OAUTH_TOKEN`.
- **O canário é uma tarefa de escrituração já existente na fila**, escolhida pela
  maestro no dia, nunca criada de propósito para passar.
- **Toda lição do despachante vai para o RUNBOOK §9** como lição de regência, e
  toda armadilha nova ganha número do almoxarife, como sempre.

## Estado

**PROPOSTO em 05/09/2026.** Esperando as quatro decisões do §8, em pergunta
estruturada, na sessão em que o mantenedor decidir voltar ao assunto. Até lá,
nada foi construído e nenhuma tarefa da escada existe na fila.
