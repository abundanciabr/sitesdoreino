# RITOS DA PLATAFORMA

Quatro ritos. Cada um fecha um modo de falha conhecido — com nome, mecânica e antídoto.

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

## §2 — Catraca Verde + Anti-Thrashing

A gênese de todo labirinto, nomeada: erro → muda A → outro erro → muda B → remove
validação → muda banco → ninguém sabe mais o que aconteceu. O antídoto tem quatro peças:

0. **Muralha de branch:** todo trabalho nasce em branch (RITOS.md §1) e chega a
   `main` só por PR com portão verde (peça 4). **A proteção nativa do GitHub está
   LIGADA desde 26/08/2026** — o repositório é público, e em repositório público
   regras de proteção e Actions são gratuitos. O conjunto de regras `main
   protegida` (ativo, `bypass_actors` vazio — ninguém escapa, nem o dono) impõe:
   PR obrigatório, proibido apagar a `main`, proibido reescrever história, e os
   checks `muralhas` e `ci-celula-gate` obrigatórios. **Desde 28/08/2026 também
   a política estrita:** PR com base velha não mergeia — é a trava da colisão
   semântica (`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`, Classe 6).

   > **Esta peça já mentiu, e custou caro.** Até 28/08/2026 ela afirmava que a
   > proteção nativa exigia plano pago e estava "fora de alcance" (H3). A frase
   > foi verdadeira por semanas e depois envelheceu sem que nada avisasse — e em
   > 28/08 foi lida com sinceridade e entregue como premissa a **cinco
   > consultorias externas**, que projetaram substitutos para uma proteção que já
   > existia. Nenhum teste pega isto: ler nunca dá erro. É a Classe 8 (mapa
   > velho) aplicada à própria lei. Se você está lendo esta peça para decidir
   > alguma coisa, **confira o estado real antes**:
   > `gh api repos/abundanciabr/sitesdoreino/rulesets`.

   Os degraus locais continuam, como cerca rápida (falham em segundos, sem
   esperar o GitHub): `.githooks/pre-push` (bloqueia push direto para `main`
   nesta máquina), o merge guardado da peça 4, o `alarme-main` (issue se a main
   quebrar) e o portão de deploy (commit não-verde não alcança a VPS — provado
   ao vivo em 22/08/2026).
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
4. **Fecho da catraca — o agente PEDE POUSO; quem mergeia é a pista (desde
   29/08/2026):** aberto o PR, o próprio agente conclui, sem pedir nem esperar o
   humano — mas o gesto final mudou de mão:

   ```bash
   python ci/mergear.py <PR> --conferir   # o portão, como sempre
   python ci/mergear.py <PR> --pousar     # tudo verde ⇒ pede pouso e SIGA
   ```

   `--confirmo` **recusa** para quem não é a pista, e a recusa diz isto aqui.
   Vermelho, pendente, ausente ou ERROR ⇒ **não se pede pouso**: conserta-se ou
   reporta-se (o `--pousar` só age com o portão verde, e reprova antes de pôr a
   etiqueta). O botão do site não é caminho para ninguém.

   **Por que mudou** (decisão do mantenedor, registro `20260829-006`): o agente
   mergeava com base em checks que rodaram ANTES de a fila andar, e a `main`
   recebe ~100 entregas por dia — ele perdia a corrida contra o próprio relógio.
   **O que NÃO mudou:** ninguém espera pelo mantenedor; quem mergeia continua
   sendo máquina.

   Depois do pouso, ao agente restam o registro no livro e, se o merge dispara
   deploy, o veredito do run (CLAUDE.md) — a pista comenta no PR o que
   aconteceu. Merge em caminho CODEOWNERS exige mandato do despacho e anúncio
   nominal no relatório (Lei 4). Se o objetivo era Pix e o diff mostra
`methods/card/` ou 42 arquivos — é o alarme dele, antes de ser o alarme do CI.

5. **A pista, por dentro — o que acontece depois que você pede pouso:**

   ```bash
   python ci/mergear.py <N> --pousar      # o caminho normal (peça 4)
   gh pr edit <N> --add-label pousar      # o mesmo gesto, na mão
   ```

   E vá embora. A pista (`.github/workflows/pouso.yml`, Onda 4 do
   `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`) atende **um PR por vez**:
   atualiza a base, confere pelo MESMO `ci/mergear.py` e mergeia. Ela não é mais
   permissiva que a catraca — é a catraca com paciência.

   **Quando usar:** o PR ficou `BEHIND` mais de uma vez, ou toca `painel/` num
   dia movimentado. Sintoma de que você está na corrida errada:
   atualizar → esperar 90s de checks → a `main` andou → repetir
   (`armadilhas/156`; medido: oito voltas num PR de 4 arquivos). **Insistir não
   é persistência, é gastar franquia contra um relógio que você não controla.**

   **O que a pista faz com o seu PR:** verde ⇒ mergeia; vermelho de verdade ⇒
   devolve com o veredito cru e TIRA a etiqueta (para não entupir a fila atrás
   dele); checks ainda rodando ⇒ **espera quieto** e volta na passagem seguinte,
   sem punir um PR são. Ela se rechama ao terminar e tem um agendamento de rede
   a cada 15 min.

   **A troca de dono ACONTECEU em 29/08/2026** (registro `20260829-006`,
   respondendo ao pedido `20260828-033`): a pista deixou de ser um atalho para
   dias movimentados e passou a ser O caminho. `ci/mergear.py --confirmo` recusa
   para quem não é ela, e a Lei 4 da `CONSTITUICAO.md` traz a emenda. A lei
   mudou junto com o mecanismo, nunca antes dele.

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
