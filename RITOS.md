# RITOS DA PLATAFORMA

Quatro ritos. Cada um fecha um modo de falha conhecido — com nome, mecânica e antídoto.

---

## §1 — Rito de Abertura de Sessão (worktree por agente)

Cada sessão de agente nasce dentro de um worktree, dentro de UMA célula. O agente só
enxerga a árvore onde nasceu — quebrar outra célula deixa de ser proibido e passa a
ser fisicamente estranho ao seu mundo.

```bash
# Na raiz do clone principal (você, ou o script de despacho):
git fetch origin
git worktree add ../wt-<celula>-<tarefa> -b agent/<celula>/<tarefa> origin/main
cd ../wt-<celula>-<tarefa>/services/<celula>    # ⟵ a sessão do agente ABRE AQUI
```

**Declaração obrigatória** (primeira linha da primeira resposta do agente):

> "Li `CONSTITUICAO.md` e `constituicoes/AGENTS.<celula>.md`. Worktree:
> `wt-<celula>-<tarefa>`. Branch: `agent/<celula>/<tarefa>`. `git status`: limpo.
> Baseline: `make ci` verde. Tarefa: [uma frase]."

Se o baseline NÃO estiver verde antes de tocar qualquer arquivo: **parar e reportar**
— consertar main quebrada não é escopo de sessão de feature.

**Dieta de contexto (lei de despacho):** todo brief nomeia arquivos-alvo, o que é
somente-leitura e a fronteira congelada. Nunca se cola a célula inteira no contexto
quando o alvo é um componente. O despacho segue o template do `CAMINHO-DOURADO.md`
e cita receitas por número — o agente carrega SÓ as citadas.

**Encerramento:** handoff registrado (branch, commits+hashes, push sim/não, feito,
pendente, riscos) + `git worktree remove` após o merge. Workspace sujo não passa
para o próximo agente: commite ou descarte explicitamente.

---

## §2 — Catraca Verde + Anti-Thrashing

A gênese de todo labirinto, nomeada: erro → muda A → outro erro → muda B → remove
validação → muda banco → ninguém sabe mais o que aconteceu. O antídoto tem quatro peças:

0. **Muralha de branch:** todo trabalho nasce em branch (RITOS.md §1) e chega a
   `main` só por PR com portão verde (peça 4). Proteção nativa do GitHub exige
   plano pago em repositório privado pessoal e está **fora de alcance** (H3 —
   não há forma de pagamento aceita; não sugira "assine o Pro"). Os degraus
   reais: `.githooks/pre-push` (bloqueia push direto para `main` nesta máquina),
   o merge guardado da peça 4, o `alarme-main` (issue se a main quebrar) e o
   portão de deploy (commit não-verde não alcança a VPS — provado ao vivo em
   22/08/2026).
1. **Catraca:** todo estado verde vira commit IMEDIATAMENTE (Conventional Commits,
   descrição em PT: `fix(pix): corrigir parsing do webhook`). Nenhum trabalho novo
   começa sobre estado não commitado. `git add` por arquivo — **nunca `git add -A`**;
   revise `git diff --cached --name-only` antes de commitar.
2. **Regra de parada:** DUAS tentativas consecutivas de correção falharam ⇒
   `git reset --hard <último-verde>` ⇒ reportar com diagnóstico. A terceira tentativa
   é onde nascem labirintos — ela não existe neste reino.
3. **Intocabilidade dos testes:** proibido deletar, desativar, comentar ou afrouxar
   teste para passar. Correção em invariante apresenta evidência falsificável:
   saída crua do guarda **vermelho sem o fix, verde com o fix**. "Eu arrumei" não
   é aceito.
4. **Fecho da catraca — o merge é do agente (desde 22/08/2026):** aberto o PR, o
   próprio agente conclui, sem pedir nem esperar o humano: espera os checks
   terminarem, confere com `python ci/mergear.py <PR> --conferir` e mergeia com
   `python ci/mergear.py <PR> --confirmo <PR>` — o `--confirmo` repete o número
   do PR de propósito (o erro real da história foi mergear o PR errado, não
   mergear sem querer). Vermelho, pendente, ausente ou ERROR ⇒ **não se mergeia**:
   conserta-se ou reporta-se. O botão do site não é caminho. Depois do merge, o
   script já confere `state=MERGED`; ao agente restam o painel e, se o merge
   dispara deploy, o veredito do run (CLAUDE.md). Merge em caminho CODEOWNERS
   exige mandato do despacho e anúncio nominal no relatório (Lei 4). Se o
objetivo era Pix e o diff mostra `methods/card/` ou 42 arquivos — é o alarme dele,
antes de ser o alarme do CI.

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
