---
schema_version: 2
armadilha: 393
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: a sabotagem e um gesto manual do robo dentro da bancada dele, e nenhum portao ve a diferenca entre "desfiz a sabotagem" e "apaguei o meu trabalho junto"; o que evita a queda e a ORDEM dos gestos, e ela mora no habito
sinal:
  - "esperava 1 ocorr.ncia, achei 0"
---

# `git checkout <arquivo>` para desfazer a sabotagem ANTES do commit apaga também os seus consertos

**Data:** 07/09/2026 · **Onde:** toda prova por mutação (RUNBOOK §9, ficha do
despacho §4) feita com o trabalho ainda não commitado · **Custo evitado:** os
consertos reaplicados do zero e duas sabotagens rodadas contra o código ERRADO
sem ninguém perceber

## Sintoma

Você editou `views.py`, os testes ficaram verdes, e foi provar por mutação:
sabotou uma linha, o teste ficou vermelho, e para "desfazer a sabotagem" rodou:

```
git checkout -q apps/core/views.py
```

O arquivo voltou ao estado do ÚLTIMO COMMIT, que não tem nenhum dos seus
consertos. A segunda sabotagem, feita por troca de texto exato, falhou com
`esperava 1 ocorrência, achei 0` porque a linha que ela queria sabotar já não
existia; a terceira "passou" verde porque rodou contra o código antigo. O
`git status` no fim mostra o arquivo LIMPO, que parece sucesso e é o sinal
da perda.

## Causa

`git checkout <caminho>` não é "desfazer a última edição": é "voltar ao
commit". Antes do commit, a sua edição e a sabotagem são a MESMA diferença
para o Git, e as duas vão embora juntas. A ficha do despacho manda "desfaça a
sabotagem antes de commitar", e lida às pressas ela convida exatamente a este
gesto.

## Solução

Commite PRIMEIRO, sabote DEPOIS. Com o conserto no commit, `git checkout` do
arquivo volta ao conserto, e a sabotagem some sozinha. É o que a ficha quer
dizer com "desfaça a sabotagem antes de commitar": nenhuma sabotagem entra no
commit, não que o commit espere a prova.

Se precisar sabotar antes de commitar (teste que só nasce com a mudança), desfaça
pela MESMA troca de texto ao contrário, ou `git stash` a sabotagem, nunca
`checkout`. E confira o `git diff --stat` depois de cada restauração: a
contagem de linhas tem de ser a de antes da sabotagem.
