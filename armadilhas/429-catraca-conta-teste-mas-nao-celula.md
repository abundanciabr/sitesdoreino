schema_version: 2
armadilha: 429
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/catraca_de_testes.py
  - ci/tests/test_catraca_de_testes.py
guarda:
  tipo: CI
  dono: ci/tests/test_catraca_de_testes.py
  detector: test_cobertura_da_celula_reprova_reducao_do_total
sinal: 'os testes de um arquivo podem ser removidos ou redistribuídos e a catraca não informa a redução da célula'
licao: 'Contar apenas o arquivo tocado não mede cobertura por célula. O portão precisa somar os testes coletáveis da célula na base e no PR e reprovar toda queda, mantendo a autorização explícita para remoções.'
---

# 429: Catraca conta teste, mas não célula

**Data:** 09/09/2026. **Onde:** `ci/catraca_de_testes.py`.

## Sintoma e causa

A catraca já detectava teste apagado ou reduzido no arquivo modificado, mas não
possuía uma régua agregada por célula. A suíte podia perder cobertura da célula
sem uma mensagem que nomeasse a queda no total.

## Solução e evidência

O portão soma os testes coletáveis de cada célula na base e no PR usando
`celulas.yml`, imprime o placar e reprova totais menores. A mutação que removeu
essa comparação deixou a prova vermelha; a implementação restaurada passou a
suíte e a execução real do portão.
