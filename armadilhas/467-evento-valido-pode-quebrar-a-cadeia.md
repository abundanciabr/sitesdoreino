---
schema_version: 2
armadilha: 467
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/fila.py
  - fila/eventos/
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
  detector: test_validador_recusa_submissao_manual_que_quebra_a_cadeia
  motivo: um evento isolado pode ter todos os campos válidos e ainda trocar a identidade sem declarar o predecessor
licao: Em histórico append-only, valide também a relação entre eventos consecutivos; mudança de identidade exige elo explícito com o último evento e motivo não vazio.
---

# 467: Um evento válido isoladamente pode quebrar a cadeia

## Sintoma

Uma tarefa já submetida aponta para outro PR depois que alguém acrescenta um
JSON com campos válidos. O arquivo anterior continua no disco, mas nada declara
que houve substituição nem por que ela ocorreu.

## Causa

O validador conferia o esquema de cada evento separadamente. Esse exame prova
que PR, revisão e árvore têm formato válido, mas não prova que a mudança de PR
se liga à última submissão. Append-only no armazenamento não garante
append-only na semântica.

## Lição

Quando um acontecimento muda a identidade vigente, valide a cadeia ordenada. O
novo evento precisa apontar exatamente para o predecessor, explicar a troca e
ser recusado se o elo aparecer na primeira submissão ou numa atualização do
mesmo PR. A repetição exata é retomada idempotente, não outro acontecimento.

## Evidência

`test_validador_recusa_submissao_manual_que_quebra_a_cadeia` reprova troca sem
elo, elo errado, elo na primeira submissão, elo no mesmo PR e motivo vazio.
Sabotar a guarda de elo fez o caso sem elo falhar isoladamente.
