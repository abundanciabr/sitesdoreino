---
schema_version: 2
armadilha: 422
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/pr.py
  - painel/gerar_manifesto.js
guarda:
  tipo: CI
  dono: ci/tests/test_pr.py
  detector: 'a validação isolada termina com fontes não rastreadas depois de gerar o painel'
sinal: 'o PR do painel falha na prova isolada porque painel.html e livro-AAAAMM.js foram criados durante a validação'
licao: 'Quando a prova do PR precisar gerar e conferir o painel, faça a geração, a conferência e a remoção dos arquivos ignorados no mesmo comando; a árvore isolada precisa terminar limpa.'
---

# 422: A validação do PR enxerga os artefatos ignorados do painel

**Sintoma.** O PR passa no gerador e no verificador local, mas `ci/pr.py` interrompe a prova isolada dizendo que existem fontes não rastreadas.

**Causa.** `painel/gerar_manifesto.js` cria `painel.html` e `livro-AAAAMM.js`. Eles são ignorados pelo Git, mas a validação fail-closed do PR inspeciona arquivos JavaScript ignorados e os trata como fontes temporárias.

**Lição.** Na validação declarada do PR, combine a geração, a conferência e a remoção dos artefatos ignorados em um único comando. Assim o painel é conferido e a árvore isolada termina limpa.

**Evidência.** A entrega da área Comunidade encontrou o bloqueio ao validar o registro pós-merge e passou depois de usar essa sequência. O PR #1436 embarcou o registro e todos os checks terminaram verdes.
