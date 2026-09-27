---
schema_version: 2
armadilha: 513
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/pr.py
sinal:
  - "árvore sem mudanças"
  - "Use --continuar para validar os commits existentes"
guarda:
  tipo: nenhum
  motivo: a recusa e o proprio guarda funcionando; ci/pr.py nao tem como saber se a arvore limpa e um commit ja feito por voce ou uma chamada vazia por engano, e as duas merecem a mesma mensagem
licao: "ci/pr.py recusa 'arvore sem mudancas' quando git status --porcelain vem vazio sem --continuar (linha 716). Acontece quando o commit da entrega ja existe antes da primeira chamada (commit manual, retomada de sessao). Confira git status --porcelain antes e chame com --continuar desde a primeira tentativa."
---

# 513: `ci/pr.py` exige `--continuar` desde a primeira chamada quando os commits já existem

**Data:** 26/09/2026 · **Onde:** `ci/pr.py`, obra Appmax · **Custo evitado:**
uma chamada perdida e a confusão de achar que o script não reconhece o
trabalho feito.

## Sintoma

```
$ python ci/pr.py --titulo "..." --arquivos ...
ParouPorSeguranca: árvore sem mudanças
Use --continuar para validar os commits existentes.
```

O comando recusa mesmo com o commit da entrega já presente no ramo: `git
status --porcelain` vem vazio porque não há nada para adicionar ao índice,
e `ci/pr.py` (linha 716-717) trata árvore limpa sem `--continuar` como
sinal de chamada vazia, não de trabalho já commitado.

## Causa

O script não distingue "não fiz nada ainda" de "já commitei e estou
retomando"; a única diferença observável do lado dele é a flag. Isso é
comum quando a mesma sessão chama `ci/pr.py` mais de uma vez (rede caiu,
push falhou, sessão foi retomada) ou quando o commit foi feito manualmente
antes da primeira chamada.

## Solução

Antes de chamar `ci/pr.py`, confira se a árvore já está limpa:

```bash
git status --porcelain
```

Vazio e você sabe que o commit já existe: chame com `--continuar` desde a
primeira tentativa. Não gaste uma chamada sem a flag só para "ver o que
acontece"; a recusa é sempre a mesma e não avança nada.

## Origem

Obra Appmax, sessões de coordenação de 26/09/2026, `ci/pr.py` linhas 716-717.
