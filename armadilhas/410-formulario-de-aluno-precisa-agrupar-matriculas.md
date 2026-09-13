---
schema_version: 2
armadilha: 410
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "A regra depende de revisão da tela e dos testes de sincronização."
sinal: null
---

# Formulário de aluno não é uma matrícula

Ao permitir mais de um curso por pessoa, a lista antiga passou a desenhar a
mesma pessoa várias vezes. O formulário precisa agrupar as linhas por escola e
e-mail, marcar somente as matrículas ativas e enviar a seleção completa.

Uma matrícula ausente deve ser criada com uma chave administrativa idempotente.
Uma matrícula suspensa marcada volta a ativa. Uma matrícula ativa desmarcada
fica suspensa. Nenhum desses gestos apaga a ficha ou reescreve o produto.
