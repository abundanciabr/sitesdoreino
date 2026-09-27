---
schema_version: 2
armadilha: 518
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o stash vive no .git compartilhado por todos os worktrees; nao ha como um portao distinguir, no momento do pop, se aquele stash pertence a bancada que esta chamando. A disciplina e nunca usar stash em bancada de worktree, so commit WIP no proprio ramo.
sinal:
  - "Dropped refs/stash@\\{0\\}"
gatilho:
  - "wt-*/"
licao: "git stash e por repositorio (.git), nao por worktree: um stash pop numa bancada aplica o WIP que outra bancada irma deixou no MESMO clone. Em worktree, commit o WIP no proprio ramo (git commit -m wip, depois amend ou squash); stash fica proibido."
---

# 518: `git stash` é compartilhado entre todos os worktrees do mesmo `.git`

**Data:** 26/09/2026 · **Onde:** duas frentes do sistema de experimentos
(F3 e F10), cada uma em seu `wt-*` · **Custo evitado:** uma frente aplicando
o trabalho da outra sem perceber, misturando dois despachos no mesmo commit

## Sintoma

Um `git stash pop` numa bancada trouxe alterações que não pertenciam àquela
tarefa: eram o WIP que outra frente (rodando em outro `wt-*` do mesmo clone)
havia deixado em stash minutos antes. As duas bancadas usam diretórios
`worktree` diferentes, mas compartilham o mesmo diretório `.git`, e o stash
mora nesse `.git`, não no worktree.

```
Dropped refs/stash@{0} (....)
```

sem nenhum aviso de que o conteúdo aplicado vinha de outra árvore de
trabalho.

## Causa

`git worktree` separa o diretório de trabalho e o índice, mas a pilha de
stash é um conjunto de commits sob refs (`refs/stash`) guardado no `.git`
comum a todos os worktrees do mesmo repositório. Um `stash pop` não filtra
por worktree de origem: ele aplica o topo da pilha, seja qual for a bancada
que o empilhou.

## Solução

Em bancada de worktree, `git stash` está proibido. Para guardar trabalho em
andamento sem perder o lugar, commite no próprio ramo:

```bash
git commit -am "wip: <o que falta>"
```

e depois `git commit --amend` ou `git reset --soft HEAD~1` para reorganizar
antes do PR final. Isso mantém o WIP dentro do ramo daquela bancada, imune a
qualquer outra sessão que rode no mesmo clone.

## Evidência

Frentes F3 e F10 do sistema de experimentos, 26/09/2026, relatadas pela
sessão que fechou o sistema de experimentos.
