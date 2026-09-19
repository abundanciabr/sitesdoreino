---
schema_version: 2
armadilha: 471
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_analise_fase4.py
  detector: test_validade_estrutural_nao_vira_completude_confirmatoria
sinal: 'um evento legível e íntegro entra na amostra sem vínculo prévio, evidência de resultado ou métricas declaradas'
gatilho:
  - ci/telemetria.py
  - ci/registrar_tarefa_fase4.py
  - ci/analise_fase4.py
licao: 'Validade estrutural só prova que o registro não foi corrompido. A coorte confirmatória exige tarefa versionada e classificada antes do início, revisão derivada do código, resultado verificável e cada métrica observada ou explicitamente nula.'
---

# 471: Evento válido não é amostra confirmatória

## Sintoma

O analisador aceitava registros cuja identidade interna conferia, mesmo sem
provar que a tarefa existia e tinha sido classificada antes da execução. Uma
estrutura antiga válida parecia evidência confirmatória e carregava para a
amostra lacunas que o próprio evento não podia explicar.

## Causa

Um único predicado respondia duas perguntas diferentes: se o JSON era íntegro
e se a observação cumpria o protocolo. A identidade também deixava de fora
campos posteriores, portanto uma reexecução podia esconder mudança de
evidência, métrica ou revisão.

## Solução

Manter a leitura estrutural dos eventos históricos e aplicar uma segunda
fronteira para a coorte. Essa fronteira confere o vínculo com a tarefa
versionada, o instante da classificação, a revisão do instrumento derivada do
código, o estado mais recente, a evidência do resultado e todas as métricas.
O diagnóstico expõe as duas contagens sem apagar nem promover o histórico.

## Evidência

As guardas do registrador e do analisador nasceram vermelhas, passaram após a
correção e reprovaram quando cada fronteira foi sabotada. A leitura real
preservou os cinco eventos privados: cinco estruturalmente válidos e zero
confirmatórios sob o contrato corrigido.
