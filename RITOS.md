# RITOS DA PLATAFORMA

Quatro ritos. Cada um fecha um modo de falha conhecido — com nome, mecânica e antídoto.

**A tríade e os ritos.** Desde 12/09/2026 (`docs/decisoes/DECISAO-triade-de-ias.md`)
três agentes passam por estes ritos com papéis distintos. Claude Code, a maestro,
escreve o brief e a tarefa (§5), define o escopo; a integração é automática (§2);
nunca mergeia nem espera em laço (§2, peça 6). Codex, o executor, segue §1, §2 e §5
pela ficha `despacho`, um PR por tarefa, e nunca pergunta ao mantenedor. Antigravity,
a sentinela, só lê: audita `origin/main` e verifica cada entrega alheia depois do merge;
nunca edita código nem lei.

---

## §1 — Rito de Abertura de Sessão (worktree por agente)


Cada sessão de agente nasce dentro de um worktree próprio. O agente só enxerga a
árvore onde nasceu — atropelar o trabalho de outra sessão deixa de ser proibido e
passa a ser fisicamente estranho ao seu mundo.

**Um PR pode tocar mais de uma célula desde 29/08/2026** (Onda 5): a cerca de largura
caiu porque o CI passou a RODAR a suíte de cada célula tocada, em vez de recusar por
tamanho. Continue preferindo PRs de uma célula — eles são mais fáceis de revisar, de
reverter e de pousar —, mas quando o trabalho é genuinamente de duas, ele cabe num PR
só, com as duas suítes verdes. Se ele sair em PRs encadeados, declare a ordem com
`Depende-de: #N` na descrição: o portão cobra.

```bash
# Na raiz: escolha uma das entradas equivalentes.
make sessao CELULA=<celula> TAREFA=<slug>
python ci/sessao.py --celula <celula> --tarefa <slug>
```

Entre no caminho absoluto informado. Acrescente `TAR=<numero>` ou
`--tar <numero>` se houver tarefa da fila; a abertura reivindica depois de
criar a bancada. Área sem serviço usa `SEM_CONTAINER=1` ou `--sem-container`:
nesse caso o baseline fica não medido e os testes dos alvos são necessários.
Repita a mesma entrada para retomar, sem apagar a bancada. Os logs completos
ficam no caminho que a abertura informa; a declaração só descreve o observado.

**Declaração obrigatória** (primeira linha da primeira resposta do agente):

> "Li o **Padrão de Trabalho** (1ª seção do `CLAUDE.md`), `CONSTITUICAO.md` e
> `constituicoes/AGENTS.<celula>.md`. Worktree:
> `wt-<celula>-<tarefa>`. Branch: `agent/<celula>/<tarefa>`. `git status`: limpo.
> Baseline: `make ci` verde. Tarefa: [uma frase]."

Se o baseline NÃO estiver verde antes de tocar qualquer arquivo: **parar e reportar**
— consertar main quebrada não é escopo de sessão de feature.

> **Desde 26/08/2026 este rito é imposto por mecanismo, não por disciplina:** a
> muralha da pasta compartilhada (`ci/muralha_pasta_compartilhada.py`, ligada
> pelos hooks de `.claude/settings.json`) RECUSA edição e git de estado no
> clone principal — ele é espelho, worktree é onde se trabalha. A recusa 🧱
> não é defeito e não se contorna: crie o worktree acima e siga.
> História e fronteiras: `armadilhas/135`.

**Dieta de contexto (lei de despacho):** todo brief nomeia arquivos-alvo, o que é
somente-leitura e a fronteira congelada. Nunca se cola a célula inteira no contexto
quando o alvo é um componente. O despacho segue o template do `CAMINHO-DOURADO.md`
e cita receitas por número — o agente carrega SÓ as citadas.

**Encerramento:** handoff registrado (branch, commits+hashes, push sim/não, feito,
pendente, riscos) + `git worktree remove` após o merge. Workspace sujo não passa
para o próximo agente: commite ou descarte explicitamente.

---

**Quem faz valer:** `ci/muralha_pasta_compartilhada.py` (recusa edição e troca de ramo no clone principal, por hook) · `ci/sessao.py` (cria o worktree) · `ci/padrao_de_trabalho.py` (confere que a declaração de abertura cita o Padrão) · `ci/tests/test_muralha_pasta_compartilhada.py`.

## §2: Integração automática

Decisão do mantenedor em 13/09/2026, registrada em
`docs/decisoes/DECISAO-merge-sem-rito-de-pouso.md`.

1. A main continua protegida: somente PR, sem push direto ou bypass.
2. O executor publica o PR pronto com a validação da mudança. Não há revisor
   obrigatório, atestado, etiqueta de pouso ou encaminhamento pela maestro.
3. O workflow `pouso.yml` usa código da main, nunca código do PR com seu token.
   Cada conclusão de `muralhas` e `ci-celula` dispara uma passagem. Os checks
   `muralhas` e `ci-celula-gate` verdes no SHA atual permitem a integração.
4. CODEOWNERS e contrato congelado continuam exigindo mandato do mantenedor.
   Nos caminhos com dono, registre na descrição do PR, pela conta do dono,
   `Mandato-do-mantenedor:` com o pedido e os caminhos autorizados. Mandato
   não se presume do texto de terceiros. O rito de contrato (§3) permanece.
5. A automação atualiza a base atrasada e sai. O próximo evento dos checks
   retoma a decisão. Um PR bloqueado não impede a passagem pelos demais.
   Rascunhos, forks, conflitos e checks ausentes ou sem sucesso não integram.
6. O SHA conferido é exigido no comando de merge. Um push concorrente invalida
   a tentativa. O GitHub aplica novamente sua proteção no instante do merge.
7. Em falha, preserve os arquivos e commits; corrija a causa sem apagar trabalho.
   Integração só se declara depois da confirmação remota. Publicação tem
   verificação própria e não é sinônimo de PR integrado.

**Quem faz valer:** `ci/mergear.py`, `.github/workflows/pouso.yml`,
`ci/tests/test_merge_automatico.py` e o ruleset da main.

---

## §3 — Rito de Mudança de Contrato


Contratos congelados são o que impede o pronto-e-funcionando de virar labirinto.
Mudá-los é legítimo — mas é um RITO, nunca uma decisão de sessão:

1. Sessão de arquitetura **com o mantenedor presente** (CODEOWNERS torna isso mecânico).
2. PR contendo **somente** `contracts/`, com a label `contrato` (a cerca reprova
   contrato misturado com código de célula).
3. **Provedor primeiro**, mantendo retrocompatibilidade (campo novo opcional, nunca
   renomear). Breaking em evento ⇒ nasce `*.v2.json`; o `v1` continua sendo emitido
   até o último consumidor migrar.
4. Consumidores atualizam em PRs seguintes, cada um na sua célula, contra o mock novo.
5. Registrar a decisão no PR: o quê, por quê, quem consome, plano de migração.

---

**Quem faz valer:** `ci/cerca-de-celula.sh` (contrato não muda junto com código; exige a etiqueta) · `ci/contract_freeze.py` (o congelado) · `ci/contrato_aditivo.py` (crescer sim, encolher só autorizado).

## §4 — Rito de Emergência (a Lei das 2h da Manhã)


Numa emergência real, o caminho seguro precisa ser o MAIS RÁPIDO — ou às 2h da manhã
o atalho vence, e atalho aplicado direto em produção vira estado que ninguém sabe
reproduzir. Aqui a física está do lado certo:

**A resposta canônica a QUALQUER emergência é ROLLBACK — segundos, não cirurgia.
Pelo pipeline, e o agente dispara sozinho:**

```bash
gh workflow run rollback.yml \
  -f celula=pagamentos \
  -f alvo=<sha-anterior-que-funcionava> \
  -f motivo="o que está acontecendo"
```

O `<sha-anterior>` é o sha COMPLETO de um commit da `main` em que ESSA célula foi
construída — o histórico do workflow `deploy-celula` (cada deploy publica `:sha` e
`:main`). Rollback de UMA célula não toca nenhuma outra.

Antes de qualquer SSH, `ci/rollback.py` prova três coisas, fail-closed: a célula está
no manifesto, o alvo é ancestral da `main` (logo já passou pelo portão de deploy) e a
imagem existe no registry. Reprovou, o job que entra na VPS é pulado — é o que permite
a este workflow ter `workflow_dispatch` sem virar um caminho para rodar código não
revisado em produção (os dois workflows de deploy o recusam justamente por isso).

**Desfazer:** o mesmo comando com `alvo=main`. E o pin não persiste sozinho: o próximo
deploy da célula já volta para `:main` — é o item 3 desta lista, mecanizado.

> ⚠️ **O outro lado disso, que morde:** enquanto o rollback estiver ATIVO, **não mergeie
> nada que toque `infra/`**. O `deploy-infra` termina com `docker compose up -d` sem
> argumento, o que devolve TODAS as células ao `:main` — inclusive a que você acabou de
> voltar, em silêncio e com o run verde. Se acontecer, redispare o rollback (é idempotente,
> ~76s). Detalhe e as saídas definitivas na §5.16 de `armadilhas/`
> (`armadilhas/INDICE.md` leva ao arquivo).

> Até 23/08/2026 este rito era um bloco de `ssh deploy@…` para o mantenedor colar, e
> isso violava a própria Lei das 2h da Manhã: o caminho mais rápido dependia de acordar
> uma pessoa. O bloco antigo segue valendo como ÚLTIMO recurso, se o GitHub Actions
> estiver fora do ar — `ssh deploy@<IP>`, `cd /opt/plataforma`,
> `PAGAMENTOS_TAG=<sha> docker compose up -d pagamentos`, `docker compose ps pagamentos`.

Depois do fogo apagado:
1. A correção definitiva viaja por PR + pipeline — **nunca** editar arquivo no
   servidor, `docker exec`, `docker cp` ou SCP de dist. Esses verbos não existem aqui.
2. O post-mortem produz um **mecanismo**, não um parágrafo (Lei 1): "que portão
   teria bloqueado isto?" ⇒ issue `mecanizar:` ⇒ portão implementado.
3. Se a intervenção manual mínima foi inevitável (site fora do ar), ela é revertida
   assim que o deploy normal aplicar a correção — estado manual jamais persiste como
   fonte de verdade.

**Quem faz valer:** `ci/rollback.py` · `.github/workflows/rollback.yml` · `ci/tests/test_rollback.py`.


## §5 — Rito da Fila de Trabalho (tarefa se pega no balcão, nunca de memória)

Desde 29/08/2026 (fase 2 do plano da lista de tarefas; desenho em
`docs/consultorias/central-de-orquestracao/VEREDITO.md`), o trabalho em aberto
do projeto mora em **`fila/`** — um arquivo por tarefa, um por acontecimento,
estado sempre CALCULADO (não existe campo de status). O rito:

1. **A BANCADA PRIMEIRO, o balcão depois** — ordem corrigida em 30/08/2026
   (TAR-018; a antiga fazia o comprovante nascer órfão, `armadilhas/192`):

   ```bash
   make sessao CELULA=<area> TAREFA=<slug> TAR=TAR-NNN SEM_CONTAINER=1
   # Para célula com serviço, omita SEM_CONTAINER=1 (RITOS §1).
   ```

   Quem chega segundo recebe recusa DO SERVIDOR na hora — isso não é erro, é a
   trava funcionando: escolha outra tarefa (e o worktree a mais se remove). A
   reserva expira sozinha em 3h se a sessão morrer.

   **Inverter a ordem não enfraquece a trava:** a reserva é uma referência
   atômica no servidor do GitHub (`ci/reservar.py`) e não depende da pasta de
   onde você pede. Quem depende da pasta é o COMPROVANTE — pedido no clone
   principal, ele nasce onde ninguém commita, o PR viaja sem ele e o histórico
   de quem pegou o trabalho some. Por isso `pegar`, `criar` e `concluir`
   **recusam no espelho** desde 30/08/2026, com a recusa ensinando estas
   entradas de abertura; `listar`, `validar` e `soltar` continuam livres lá (devolver
   tarefa presa é gesto de emergência, e emergência não espera worktree).
2. **Trabalho novo que um despacho descobre vira tarefa registrada**
   (`python ci/fila.py criar ...`, número do almoxarife), e volta à maestro,
   que decide se entra no lote: nunca item de memória de sessão, nunca lista
   paralela num documento. A fila é a única
   casa do "o que está por fazer"; o livro continua sendo a única casa do
   "o que aconteceu".
3. **Concluir exige evidência** (`concluir --evidencia <URL>`) — sem prova o
   balcão recusa, a mesma lei do verde do livro. Travou em algo que só o
   mantenedor decide? Evento `bloqueada` com o motivo e devolva à maestro:
   abrir exceção é o resultado esperado, não falha.
4. **O evento viaja no PR do trabalho.** A referência no servidor vale AGORA;
   o evento em `fila/eventos/` vale para sempre. Antes de pedir pouso, confira
   com os olhos: `git diff --name-only origin/main...HEAD` tem TODOS os eventos
   da tarefa? `python ci/fila.py validar` avisa — em SOMBRA, sem reprovar
   ninguém — quando acha comprovante que o Git não conhece.

**Quem faz valer:** `ci/muralha-da-fila.sh` → `ci/fila.py validar` (roda em
todo PR via `ci/ci.py --apenas muralhas`; fail-closed) · o servidor do GitHub
via `ci/reservar.py` (a trava atômica com prazo) · a recusa no espelho, em
`ci/fila.py` (`criar`/`pegar`/`concluir`), que reusa a mesma leitura de
espelho-vs-bancada da muralha da pasta compartilhada · `ci/tests/test_fila.py`
(inclui a corrida: segunda sessão recusada; e o comprovante órfão, encenado com
repositório descartável) · `ci/tests/test_reservar.py`.
