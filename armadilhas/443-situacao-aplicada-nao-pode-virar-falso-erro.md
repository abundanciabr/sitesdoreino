---
schema_version: 2
armadilha: 443
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "O teste do formulário mede que dados iguais não geram uma segunda atualização recusada."
sinal: null
---

# Situação aplicada não pode virar falso erro

O formulário envia vários campos junto com a situação. Se a situação for salva
primeiro e os outros campos, que não mudaram, forem enviados depois, a segunda
chamada pode responder que não havia nada para mudar. A tela então acusa falha
mesmo tendo aplicado o acesso pedido. O formulário deve filtrar os campos iguais
antes da segunda chamada.
