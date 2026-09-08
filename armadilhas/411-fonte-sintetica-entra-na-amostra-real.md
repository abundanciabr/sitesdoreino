schema_version: 2
armadilha: 411
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_analise_fase4.py
  detector: test_sintetico_e_excluido_e_fica_explicado_no_diagnostico
sinal: 'a análise da Fase 4 conta uma fonte de teste como observação operacional'
gatilho:
  - ci/analise_fase4.py
  - ci/telemetria.py
  - docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md
licao: 'Fonte sintética pode ter identidade válida e ainda assim não ser uma observação operacional. O analisador deve excluí-la antes da amostra, contar a exclusão e manter a prova do cenário controlado separada da tarefa real.'
---

# 411: Fonte sintética aceita não é amostra operacional

**Data:** 08/09/2026. **Onde:** retomada da coleta da Fase 4.

## Sintoma e causa

Os fixtures dos testes da análise usavam uma identidade válida e a fonte
`telemetria-de-teste`. O analisador aceitava qualquer identidade válida como
amostra, então um cenário controlado poderia aparecer no relatório como tarefa
operacional.

## Solução

O analisador identifica fontes sintéticas, exclui esses registros antes da
consolidação, conta a exclusão no diagnóstico e conserva o caso operacional
real em separado. O teste-guarda prova que a amostra fica vazia quando só há
fixture sintético.

## Evidência

`python -m pytest ci/tests/test_analise_fase4.py ci/tests/test_registrar_tarefa_fase4.py ci/tests/test_metricas_percurso.py -q` retornou `63 passed`. A análise real reconheceu a TAR-280 e manteve a TAR-282 fora do caderno privado.
