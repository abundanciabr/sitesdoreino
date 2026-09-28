---
schema_version: 2
armadilha: 417
estado: aposentada
degrau: 3
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/mergear.py
  - ci/divida_do_livro.py
guarda:
  tipo: nenhum
  motivo: Cobrança de dívida retirada por decisão do mantenedor em 28/09/2026.
sinal: 'o portão cobra dívida de registros que existem na origin/main, mas não existem no clone local'
licao: A cobrança de dívida do livro foi retirada por decisão do mantenedor em 28/09/2026; esta entrada preserva apenas o histórico da regra antiga.
---

# 417: O portão julga o livro por um espelho atrasado

**Sintoma.** A pista encontra dívida no clone principal mesmo quando os registros que pagam os merges já estão em `origin/main`.

**Causa.** `ci/divida_do_livro.py` lê `painel/registros/` do diretório atual. Um clone atrasado pode não conter os registros mais recentes, então a cobrança fica falsa.

**Lição.** O portão mede `git rev-list --count HEAD..origin/main` antes de julgar o livro. Atraso, ref ausente, saída inválida ou erro do Git viram `ERROR`, com a instrução para armar a espera de uma bancada em dia.

**Evidência.** A guarda foi quebrada para ignorar o atraso e o teste terminou vermelho; restaurada, `ci/tests/test_mergear.py` passou com 100 testes.
