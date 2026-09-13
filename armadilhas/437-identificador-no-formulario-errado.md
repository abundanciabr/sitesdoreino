---
schema_version: 2
armadilha: 437
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "A regra é protegida pelo teste que mede o formulário de salvamento."
sinal: null
---

# O identificador do aluno precisa estar no formulário que salva

Uma tela pode ter mais de um formulário para a mesma pessoa. Colocar `pessoa_email`
no formulário de liberação não ajuda o formulário de cursos: sem o identificador,
o POST cai no caminho antigo e ignora os checkboxes. Cada formulário que aciona
uma operação precisa carregar explicitamente a identidade que essa operação usa.
