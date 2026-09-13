---
schema_version: 2
armadilha: 436
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/esperar.py
  - ci/tempos_esperados.json
guarda:
  tipo: CI
  dono: ci/tests/test_espera.py
  detector: 'test_sem_teto_da_cli_usa_o_teto_da_regua_viva: a chamada sem --teto registra o prazo calculado do arquivo versionado'
sinal: 'a espera continua com um numero fixo na chamada embora a regua oficial ja meca a duracao'
licao: 'O wrapper deve calcular o teto a partir da regua viva e recusar quando nao houver medicao, mantendo --teto apenas como override explicito para uma espera sem regua.'
---

# 436: Teto manual ignora a régua viva

## Sintoma

Uma espera usa `ci/esperar.py` com um número repetido na chamada. A duração
real do CI muda, mas o robô continua morrendo cedo ou esperando além do
necessário.

## Causa

O wrapper exigia `--teto` em toda chamada, apesar de já carregar a medição
versionada em `ci/tempos_esperados.json`.

## Lição

Sem `--teto`, o wrapper calcula duas vezes o p90 da régua quando a amostra é
suficiente, ou usa uma folga sobre o p50 quando ela é pequena. Sem régua
válida, ele para e explica como fornecer uma medição ou um teto manual.

## Evidência

`python -m pytest ci/tests/test_espera.py -q` passou com 57 testes. A
contraprova trocando o cálculo por 420 segundos fez
`test_sem_teto_da_cli_usa_o_teto_da_regua_viva` reprovar porque a régua atual
calcula 600 segundos para deploy-celula.
