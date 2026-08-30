---
schema_version: 2
armadilha: 214
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: a isenção do porteiro cobre só `painel/`; alargá-la para `fila/` é mudança em ci/divida_do_livro.py, com teste-guarda, e merece PR próprio
sinal:
  - `merge\(s\) entraram na main e NINGUÉM contou ao dono`
---

# Seu PR não pousa por uma dívida do livro que não é sua, e o devedor é um PR que só escriturava

**Sintoma:** você pede pouso e o portão recusa antes de olhar os seus checks:

```
  dívida do livro   FAIL   1 merge(s) sem registro

1 merge(s) entraram na main e NINGUÉM contou ao dono:
  #597  2026-08-30  livro+fila: a gestao da Caixa mora num lugar so
```

O PR citado não é seu, entrou horas antes, e **nem código tinha**: só um registro
em `painel/registros/` e dois eventos em `fila/eventos/`.

**Causa — a isenção do porteiro é mais estreita do que a categoria que ela quer
cobrir.** `ci/divida_do_livro.py` isenta "PR que só toca `painel/`", com o
argumento correto de que esse PR **é** o registro; cobrar um registro sobre ele
seria circular. Mas fechar uma tarefa no balcão escreve em `fila/eventos/`, e é
o gesto NORMAL de quem termina um trabalho: o registro e o fechamento viajam
juntos. Um PR de escrituração pura com as duas coisas cai fora da isenção e vira
dívida.

E a dívida do livro é **compartilhada**: ela trava a fila de pouso de todo
mundo, não só de quem a criou.

**Solução — imediata:** pague. Confira o merge de verdade
(`gh pr view <N> --json state,mergedBy,mergeCommit`), escreva UM registro novo
citando o número na `evidencia`, e mande num PR mínimo de um arquivo. Depois
**rebase o seu PR na `main`**: o portão lê `painel/registros/` da SUA árvore, não
do servidor, então enquanto o seu ramo não enxergar o registro novo ele continua
acusando a mesma dívida — foi o segundo tropeço, logo depois do primeiro.

**Solução — de verdade:** alargar a isenção para "só `painel/` **e/ou**
`fila/`". É mudança em `ci/divida_do_livro.py` com teste-guarda, e enquanto não
acontecer isto se repete toda vez que alguém fechar tarefa e registrar no mesmo
PR — que é o caminho normal, não a exceção.

**Contexto:** caiu em 30/08/2026, durante a escada da regra do travessão. Custou
dois PRs de rodeio (`#606` para pagar, e um rebase do `#603`) num trabalho que
não tinha relação nenhuma com a Caixa de Sugestões.
