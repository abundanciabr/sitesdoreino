---
schema_version: 2
armadilha: 430
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "A regra é protegida pelo teste de regressão do salvamento de cursos."
sinal: null
---

# O status geral do formulário não pode desfazer a pausa por curso

Ao salvar cursos de um aluno, o campo geral `status` também viaja no formulário.
Se a tela pausa uma matrícula desmarcada e depois reaplica `status=ativa`, o
curso volta a ficar ativo. Quando cursos são a fonte de verdade da seleção, o
status geral não pode desfazer a sincronização por curso.
