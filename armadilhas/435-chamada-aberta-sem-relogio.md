---
schema_version: 2
armadilha: 435
estado: documentada
degrau: 2
confianca: alta
guarda:
  tipo: teste
  dono: services/encomendas/tests/test_inv_j11_chamada_aberta_tem_fim.py
gatilho: services/encomendas/apps/encomendas/tique.py
licao: "Estado que só sai por ação humana precisa de prazo histórico no tique"
---

# Chamada aberta sem relógio fica presa

`ABERTA` era a única saída da fila que dependia de aceite humano e não tinha
reavaliação posterior. O simulador classificava isso como buraco conhecido,
permitindo que uma encomenda órfã permanecesse ali sem limite.

A saída correta é usar o mesmo tique de um minuto, ler um parâmetro histórico e
mudar para `PARA_RECLASSIFICAR`, que já é a fila do plantão. Não criar timer novo
nem outra sessão do motor de oferta.
