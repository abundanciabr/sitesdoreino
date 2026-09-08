---
schema_version: 2
armadilha: 400
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_metricas_percurso.py
  detector: test_reinicio_de_fechamento_na_mesma_identidade_nao_fica_concluido
sinal: 'percurso completo reúne fases de tarefas diferentes ou esconde uma retomada'
gatilho:
  - ci/metricas_da_fabrica.py
  - ci/telemetria.py
licao: 'Presença global não comprova percurso individual. Separe tarefa, tentativa e revisão; preserve horários de reexecução mesmo ao deduplicar o fato lógico. Uma fase reiniciada não continua concluída por causa da primeira observação.'
---

# 400: Presença global não prova percurso individual

## Sintoma

Na auditoria corretiva F1-04, uma tentativa com fechamento iniciado às 00:01,
concluído às 00:02 e reiniciado às 00:03 ainda aparecia concluída. No sentido
inverso, uma validação recuperada após falha continuava reprovada.

## Causa

A deduplicação guardava apenas o primeiro horário do mesmo fato. Selecionar o
último estado depois disso não recuperava a transição perdida. O resumo global
também podia reunir fases de tarefas que nunca completaram um percurso.

## Solução

Consolidar horários distintos em `observado_em`, mantendo um fato lógico por
identidade. Expor cobertura por tarefa/tentativa/branch, revisão e PR. O estado
vem da observação mais recente; empate incompatível é inconclusivo. Validação
e fechamento precisam referir a revisão entregue. Não inferir dispensa de uma
fase nem importar a publicação de outra sessão para a tentativa local.

## Evidência

Dois cenários da revisão independente nasceram vermelhos e passaram após a
correção; `test_cobertura_global_nao_completa_tarefas_distintas` e as regressões
de reinício e revalidação impedem os falsos positivos. As mutações são executadas
em cópias temporárias, preservando a bancada original.
