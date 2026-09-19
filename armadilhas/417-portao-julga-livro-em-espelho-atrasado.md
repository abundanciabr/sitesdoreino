---
schema_version: 2
armadilha: 417
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/mergear.py
  - ci/divida_do_livro.py
guarda:
  tipo: CI
  dono: ci/tests/test_mergear.py
  detector: 'test_o_portao_recusa_julgar_o_livro_de_arvore_atrasada: árvore atrás de origin/main termina em ERROR'
sinal: 'o portão cobra dívida de registros que existem na origin/main, mas não existem no clone local'
licao: 'Antes de julgar a dívida do livro, confirme que HEAD está em dia com origin/main; se a medição não for possível ou houver atraso, recuse com instrução para armar a espera numa bancada em dia.'
---

# 417: O portão julga o livro por um espelho atrasado

**Sintoma.** A pista encontra dívida no clone principal mesmo quando os registros que pagam os merges já estão em `origin/main`.

**Causa.** `ci/divida_do_livro.py` lê `painel/registros/` do diretório atual. Um clone atrasado pode não conter os registros mais recentes, então a cobrança fica falsa.

**Lição.** O portão mede `git rev-list --count HEAD..origin/main` antes de julgar o livro. Atraso, ref ausente, saída inválida ou erro do Git viram `ERROR`, com a instrução para armar a espera de uma bancada em dia.

**Evidência.** A guarda foi quebrada para ignorar o atraso e o teste terminou vermelho; restaurada, `ci/tests/test_mergear.py` passou com 100 testes.
