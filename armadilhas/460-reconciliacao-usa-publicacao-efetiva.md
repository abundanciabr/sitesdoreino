---
schema_version: 2
armadilha: 460
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/fila.py
  - ci/estado_da_entrega.py
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
  detector: "uma entrega recuperada usa as URLs de publicacoes, sem aceitar o run histórico falho como prova"
  motivo: "estado terminal por cobertura posterior precisa apontar para os jobs que realmente publicaram a entrega"
licao: "Ao reconciliar uma publicação recuperada, use as provas efetivas calculadas em publicacoes; a lista runs preserva a tentativa histórica e pode continuar vermelha sem contradizer o estado terminal."
---

# Reconciliação usa a publicação efetiva

Uma publicação falha pode ser coberta depois por jobs verdes de commits que
contêm a entrega. O leitor preserva a tentativa original em `runs` para não
reescrever a história e expõe a cobertura em `publicacoes`.

Quem fecha a tarefa precisa apontar para essa cobertura. Exigir que o histórico
inteiro esteja verde impede encerrar uma recuperação válida; aceitar a URL da
tentativa falha chama de prova justamente o acontecimento que não publicou.
