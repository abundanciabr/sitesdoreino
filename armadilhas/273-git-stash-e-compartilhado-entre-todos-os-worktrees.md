---
schema_version: 2
armadilha: 273
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: um varredor teria de proibir `git stash` inteiro, e ele é legítimo num repositório de worktree único; o que existe aqui é a regra escrita e o caminho alternativo (mover o arquivo para o scratchpad), porque a recusa certa depende de saber quantos worktrees o repositório tem
sinal:
  - 'stash@{0}: WIP on agent/'
---

# `git stash pop` traz o trabalho de OUTRA sessão: a pilha é do repositório, não do seu worktree

**Sintoma.** Você guarda uma mudança sua com `git stash push`, roda um teste, e
faz `git stash pop` para desfazer. Em vez do seu arquivo, voltam mudanças que
você nunca escreveu, em arquivos que a sua tarefa não toca. Ou, pior: o `pop`
funciona, e o trabalho não commitado de outro agente some da pilha dele.

**Causa.** A pilha de stash mora em `.git/refs/stash`, e **os worktrees dividem o
mesmo `.git`**. Neste projeto isso não é detalhe: são mais de 180 bancadas
(`git worktree list`), e a pilha tem stashes de sessões antigas:

```
stash@{0}: WIP on agent/admin/menu-do-topo-tela: ...
stash@{1}: WIP on agent/caixa/tar023: ...
stash@{3}: On agent/checkout/healthz-path-info: RESGATE lote: stash do agente quiz…
```

`git stash pop` sem argumento aplica **`stash@{0}`**, que é o topo da pilha
GLOBAL — quase nunca o seu.

O jeito de cair é este, e ele parece inofensivo:

```bash
git stash push -- arquivo.py && ...testes... ; git stash pop
```

Se o `push` não guardar nada, ele **falha** (nada a guardar) e não empilha nada.
O `;` faz o `pop` rodar assim mesmo, e ele desempilha o stash de outra pessoa. O
caso mais fácil de disparar: `git stash push -- <caminho>` de um arquivo
**untracked** — o stash ignora não rastreados sem `-u`, então "não há o que
guardar" acontece justamente quando você acabou de criar um arquivo novo.

**Solução — para desfazer temporariamente, não use a pilha.** Mova o arquivo
para o scratchpad da sessão, que é seu e de mais ninguém:

```bash
mv caminho/do/arquivo.py "$SCRATCH/arquivo.py.guardado"
...rodar a suíte, ver o vermelho...
mv "$SCRATCH/arquivo.py.guardado" caminho/do/arquivo.py
```

Se ainda assim precisar do stash, duas regras: **nunca `pop` sem referência**
(`git stash pop stash@{N}`, com o `N` conferido em `git stash list` logo depois
do seu `push`), e **nunca encadeie o `pop` com `;`** — use `&&`, para que um
`push` que falhou não deixe o `pop` acontecer.

**Por que o custo é alto.** O pedido do mantenedor em 29/08/2026 é explícito:
não apagar as bancadas, porque trabalho não commitado já morreu numa delas. Um
`pop` cego é exatamente essa perda, com um agravante: ele acontece em silêncio,
no worktree errado, e o dono do stash só descobre horas depois, quando volta
para a bancada dele e a pilha está mais curta.

**Origem:** 01/09/2026, na tarefa da escada de degraus (PR #838 e seguintes). A
prova vermelho→verde de um comando NOVO exige tirar o código do caminho, e o
`git stash push` de um arquivo untracked falhou. O `pop` só não aplicou o stash
alheio porque o `cd` que vinha antes dele no mesmo comando também falhou, e o
`git` acabou rodando fora de um repositório. Foi sorte, e sorte não é guarda.
