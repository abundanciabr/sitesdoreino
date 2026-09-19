---
schema_version: 2
armadilha: 442
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/fila.py
  - fila/eventos/
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
  detector: 'test_zelador_nao_rotula_tarefa_terminal: o zelador ignora tarefas com concluida ou cancelada'
sinal: 'uma tarefa concluída ou cancelada recebe reivindicacao_expirada quando outra aquisição limpa órfãos'
licao: 'A limpeza de reivindicações deve considerar os eventos terminais antes de olhar o último ciclo. Histórico terminado não pode ser reaberto por uma rotina de manutenção.'
---

# 442: O zelador ressuscita tarefa terminada

## Sintoma

Ao pegar uma tarefa nova, o zelador percorre reivindicações antigas. Se uma
tarefa já concluída ou cancelada ainda tiver uma reivindicada anterior, ele
acrescenta reivindicacao_expirada e faz o histórico parecer reaberto.

## Causa

O cálculo do último ciclo ignorava concluida e cancelada. A rotina encontrava a
reivindicada antiga e não conferia se a tarefa já tinha chegado ao fim.

## Lição

Antes de rotular órfãos, a rotina precisa separar tarefas com evento terminal.
O histórico é somente acréscimo, mas acréscimo depois do fim também reescreve a
história.

## Evidência

`python -m pytest ci/tests/test_fila.py -q -k zelador` passou com quatro testes,
incluindo a guarda de tarefa terminal.
