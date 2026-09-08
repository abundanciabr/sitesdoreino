---
schema_version: 2
armadilha: 402
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_analise_fase4.py
  detector: test_sem_tarefas_medidas_nao_declara_ganho
sinal: 'o instrumento lê telemetria histórica, mas não consegue identificar tarefas comparáveis'
gatilho:
  - ci/telemetria.py
  - ci/analise_fase4.py
  - docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md
licao: 'Eventos de fases anteriores não formam uma amostra da Fase 4. Sem tarefa, tentativa, condição, classificação, relógio, custo e fonte, o analisador deve dizer em coleta ou não avaliável; nunca converter ausência em zero nem liberar expansão.'
---

# 402: Telemetria sem unidade de tarefa não mede piloto

**Data:** 08/09/2026. **Onde:** abertura da análise da Fase 4.

## Sintoma e causa

O caderninho privado tinha 2.183 eventos históricos, mas nenhum evento com a
identidade de tarefa medida. As fases registradas preservavam percurso e
tentativa, porém não diziam a condição antes ou depois, o tipo e a
complexidade, o relógio do resultado, o custo completo ou a fonte da medida.

## Solução

`registrar_tarefa` passou a registrar a unidade confirmatória no mesmo
caderninho. `analise_fase4.py` deduplica pela identidade da tarefa, ignora o
formato antigo e bloqueia benefício quando faltam amostra, pares, qualidade ou
custo. A ausência aparece como coleta, inconclusivo ou não avaliável.

## Evidência

`python ci/analise_fase4.py --local` encontrou 0 tarefas válidas e classificou
os três pilotos como não avaliáveis. A seleção focada final passou com 124
testes. O resultado não foi usado para declarar ganho ou iniciar expansão.
