---
schema_version: 2
armadilha: 438
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/metricas_da_fabrica.py
guarda:
  tipo: CI
  dono: ci/tests/test_metricas_da_fabrica.py
  detector: 'test_a_fila_do_dono_se_divide_pela_frente_do_livro: registros em fabrica, site e sem frente mantêm as três contagens'
sinal: 'o boletim mostra apenas o total de pedidos ao dono e não revela qual frente está acumulando decisões'
licao: 'A divisão da fila do dono deve ser calculada da mesma caixa de entrada do painel, agrupando o registro interno pela frente e preservando sem frente como estado explícito.'
---

# 438: O total do dono esconde a frente

## Sintoma

O boletim informa quantas decisões esperam pelo mantenedor, mas não mostra em
qual frente elas estão acumuladas.

## Causa

O contador já usava a caixa de entrada do painel, porém descartava cada
registro depois de contar o tamanho da lista.

## Lição

Leia a mesma caixa uma vez, preserve o total e agrupe `registro.frente`.
Registros sem frente ficam em `sem frente`, nunca desaparecem nem são
distribuídos por chute.

## Evidência

`python -m pytest ci/tests/test_metricas_da_fabrica.py -q` passou com 18
testes. A contraprova que trocou o acesso a `registro.frente` por uma constante
fez `test_a_fila_do_dono_se_divide_pela_frente_do_livro` reprovar com três
pedidos em `sem frente`.
