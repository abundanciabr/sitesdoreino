---
schema_version: 2
armadilha: 455
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
gatilho:
  - services/cursos/apps/cursos/management/commands/marcar_bosses_primeiros_dolares.py
guarda:
  tipo: CI
  dono: services/cursos/tests/test_marcar_bosses_primeiros_dolares.py
  detector: "o comando aceita variação mecânica de grafia e lista as aulas quando não encontra o Boss"
  motivo: "um deploy não pode parar com zero encontrado sem mostrar o que a base realmente tem"
licao: "Quando um comando de publicação precisa casar um título humano já existente, compare por chave normalizada e, se ainda não houver exatamente um alvo, liste as aulas do módulo antes de parar sem gravar."
---

# Título humano em deploy precisa diagnóstico

Título de aula é obra, e obra muda de caixa, acento e pontuação sem virar outra
encomenda. Um comando de publicação que casa título humano precisa separar a
variação mecânica da divergência real.

A divergência real continua parando tudo antes de gravar, mas a mensagem precisa
mostrar as aulas encontradas no módulo. Sem essa lista, a próxima sessão fica
cego diante da produção e repete o mesmo deploy para descobrir a mesma ausência.
