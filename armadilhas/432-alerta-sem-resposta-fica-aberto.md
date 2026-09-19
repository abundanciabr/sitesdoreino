---
schema_version: 2
armadilha: 432
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "O alerta só desaparece quando a resposta aponta para o registro original e a publicação tem prova externa."
sinal:
  - registro âmbar sem responde_a
  - PR mergeado e deploy verde
  - área Alunos
gatilho:
  - painel/registros/*
  - painel/LEIA-ME.md
licao: um registro verde posterior não fecha um alerta antigo sozinho. Conferir o PR, o deploy e a tela publicada; depois criar um único registro novo do tipo resposta com responde_a apontando para o arquivo original. Nunca editar ou apagar o histórico.
---

# 432: entrega publicada não fecha alerta sem resposta ao registro original

Um alerta antigo pode continuar aberto mesmo quando a correção já foi mergeada
e publicada, se os registros posteriores apenas repetirem a entrega sem
`responde_a`. A prova externa confirma o fato, mas o mecanismo do painel só
encerra a pendência quando existe uma resposta ligada ao registro que a abriu.

O fechamento correto é uma única resposta nova, com o PR mergeado, o deploy e
a tela publicada na evidência. Registros antigos continuam intactos.
