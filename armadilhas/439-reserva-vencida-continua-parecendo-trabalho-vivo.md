---
schema_version: 2
armadilha: 439
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
  detector: 'test_pegar_roda_o_zelador_antes_de_travar_a_proxima_tarefa: a aquisição marca a reivindicação órfã antes de criar a próxima'
sinal: 'uma tarefa permanece reivindicada mesmo depois de a reserva vencer e de não existir PR aberto'
licao: 'A limpeza deve ser append-only e preguiçosa: ao adquirir, conferir a validade da reserva e registrar reivindicacao_expirada quando não houver reserva viva nem PR aberto. Ramos e PRs nunca são apagados.'
---

# 439: Reserva vencida continua parecendo trabalho vivo

## Sintoma

Uma sessão morre, a reserva vence e o PR nunca nasce. A tarefa continua com o
rótulo reivindicada, impedindo a fila de oferecê-la de novo.

## Causa

O quadro conhecia a referência remota, mas não conferia o campo `expira_em`.
Também não havia um acontecimento para registrar que a reivindicação perdeu a
trava.

## Lição

O zelador confere a reserva no servidor e o PR aberto antes de marcar o órfão.
Ele acrescenta `reivindicacao_expirada`, devolve a tarefa à fila e preserva
todos os ramos, PRs e referências remotas para auditoria.

## Evidência

`python -m pytest ci/tests/test_fila.py -q` passou com 104 testes. A mutação que
removeu a proteção de PR aberto reprovou `test_zelador_preserva_reivindicacao_que_tem_pr_aberto`.
