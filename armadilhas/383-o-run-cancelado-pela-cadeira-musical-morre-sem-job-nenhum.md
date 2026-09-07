---
schema_version: 2
armadilha: 383
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: ci/tests/test_rerun_de_deploy.py
sinal:
  - `gh run view .* --json jobs` de um cancelado devolve lista vazia
  - plano que manda ler o `output` do job `detectar` daquele mesmo run
gatilho:
  - ci/rerun_de_deploy.py
licao: run cancelado pela cadeira musical morre PENDENTE, com ZERO jobs — a matrix dele nunca existiu para ser lida. Reconstrua-a do diff do push (`git diff <sha>^...<sha>` + `celulas.yml`), que é a mesma conta do job `detectar`.
---

# O run cancelado pela cadeira musical morre sem job nenhum: a matrix dele nunca existiu

**Sintoma.** Você precisa saber o que um deploy cancelado ia construir. O plano
na sua frente (o despacho da `TAR-210`, escrito a partir da `armadilhas/359`)
manda a fonte: *"o job `detectar` daquele mesmo run já sabe"*. Você abre o run
para ler, e ele não tem job nenhum:

```bash
gh run view 34048495577 --json jobs --jq '[.jobs[]|"\(.name):\(.conclusion)"]'
# (vazio)
```

Medido em 07/09/2026 nos CINCO últimos cancelados do `deploy-celula` (runs
34048495577, 34048245140, 34047959407, 34047500383 e 34046876458): **cinco de
cinco com zero jobs**.

**Causa.** O `concurrency` do `deploy-celula.yml` é `group: deploy` com
`cancel-in-progress: false`, e o GitHub guarda **um** run pendente por grupo.
O cancelamento da `armadilhas/188` acontece com o run ainda na FILA: ele é
expulso da vaga de pendente antes de começar, então nenhum job chega a nascer
— nem o `detectar`, nem o `portao-de-deploy`. Não é que a leitura seja difícil;
é que não há o que ler.

E a leitura de um run que RODOU também engana pelo lado oposto. O run
34001330286, o do incidente da `armadilhas/359`, hoje mostra
`deploy (mensageria): success` e `deploy (admin): failure` — porque foi
redisparado à mão depois, e o `gh run view` mostra o ÚLTIMO attempt, não o
estado que a entrada registrou. Quem lê o run dias depois vê outro mundo.

**Solução.** Refaça a conta de fora, com a MESMA fonte que o job `detectar`
usa: o diff do push contra `celulas.yml`.

```bash
git diff --name-only <sha>^...<sha>   # o intervalo do push
python ci/ci.py --detectar-celulas --base <sha>^   # a mesma conta, no HEAD atual
```

O primeiro pai de um merge commit da pista É o topo anterior da `main`, ou
seja, o `github.event.before` daquele push. Conferido em 07/09/2026 contra os
25 últimos runs do `deploy-celula`: nos 24 que tinham jobs, a conta devolveu
exatamente a matrix real, célula por célula (o 25º ainda estava rodando, sem
jobs criados). É o que `ci/rerun_de_deploy.py::celulas_do_push` faz.

**A lição maior, e ela não é sobre YAML.** O despacho nomeava uma fonte que não
existe, e nomeava com confiança. Se eu tivesse construído em cima dela, a
vacina só enxergaria o caso raro (o run que chegou a rodar) e continuaria cega
no caso comum (o expulso da fila) — entregando meia cura com teste verde. Uma
fonte de dado citada num plano é uma AFIRMAÇÃO a medir antes da primeira linha
de código, não um fato dado. Custou cinco chamadas de `gh` e salvou a tarefa.

**Origem.** 07/09/2026, `TAR-210`, ao abrir os cancelados reais para montar o
teste-guarda da `armadilhas/359`. **Categoria**
(`RETROSPECTIVA-FASE-D`): garantia sem mecanismo (a fonte suposta nunca tinha
sido medida) · falso-verde (a meia cura passaria em todos os testes que o
próprio despacho pedia).

**Vizinhas.** `armadilhas/359` (o furo que esta tarefa fechou — ela é quem
citava a fonte inexistente) · `armadilhas/188` (a cadeira musical que expulsa o
pendente, e é ela que deixa o run sem jobs) · `armadilhas/183` (o `gh run
rerun` devolve 0 só por enfileirar: outro caso de ler do Actions uma resposta
que parece dizer mais do que diz).
