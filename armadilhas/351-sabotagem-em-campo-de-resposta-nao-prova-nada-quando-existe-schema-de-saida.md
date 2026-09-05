---
schema_version: 2
armadilha: 351
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe que a prova de mutação foi feita contra o dicionário de retorno em vez do Schema; o CI vê a suíte verde nos dois casos. A cura é de MÉTODO, e cabe numa frase - a sabotagem tem de mudar o que o Schema deixa passar, não o que a view calculou por dentro.
sinal:
  - "sabotei e continuou verde"
  - "response="
  - "django-ninja"
  - "Schema de saída"
  - "campo extra no retorno"
---

# Sabotagem em campo de resposta não prova nada quando existe um Schema de saída

**Sintoma.** Na prova por mutação exigida depois do verde (Lei 6), você
sabota um guarda comentando ou alterando o que a view calcula, o teste
correspondente continua **verde**, e a leitura mais fácil é "o guarda não
protege nada". Ela está errada: o guarda pode estar certo, e a sabotagem é que
não chegou aonde precisava.

**Causa.** Em django-ninja (e em qualquer framework com serializador de
saída declarado), a rota tem `response=AlgumSchema`. Todo campo que a view
põe no dicionário de retorno e que **não está listado no Schema** é
**descartado antes de sair** — o cliente do endpoint nunca o vê. Sabotar
acrescentando um campo extra ao dicionário (um total geral, uma contagem a
mais) muda o que a view calculou, mas não muda o que o Schema deixa passar:
o teste que lê a resposta HTTP continua vendo exatamente o mesmo contrato de
antes, porque é isso que o Schema garante.

Medido no PR #1114 (célula `metricas`), em 05/09/2026: de 14 sabotagens
feitas na prova de mutação, **3 eram falsas por esta classe de engano**, e as
três teriam sido dadas como "guarda provado" se o robô não tivesse estranhado
o verde. Duas outras sabotagens da mesma rodada eram falsas por motivos
vizinhos, e valem como exemplo de como o mesmo sintoma nasce de causas
diferentes:

- **O cenário de teste não tinha o dente que a sabotagem precisava para
  aparecer.** A sabotagem trocava a chave de agrupamento por um tipo que não
  batia entre os dois vocabulários somados; mas o cenário de teste só usava
  UM vocabulário, então não havia nada para fundir errado, e o teste passava
  por falta de caso, não por falta de guarda.
- **A rota sabotada continuava contando como rota.** Renomear o nome da rota
  não muda quantos caminhos o Schema de listagem de rotas enumera: a
  sabotagem certa ali era remover o decorador que registra a rota, não seu
  nome.

**Solução.** Antes de sabotar, pergunte uma frase: **o que exatamente este
guarda impede o usuário do código de receber?** Sabote ISSO, não a variável
mais fácil de comentar dentro da função. Na prática, para uma rota com
`response=Schema`:

1. Rode o teste sabotado e leia a resposta HTTP que ele recebeu, não só o
   veredito verde/vermelho — se a resposta é idêntica à do caso correto, a
   sabotagem não mudou nada que o contrato exponha.
2. Se o campo sabotado não está no `Schema`, a mutação certa é no PRÓPRIO
   `Schema` (remover o campo, trocar o tipo) ou na regra de negócio que
   alimenta um campo que já está lá — nunca num campo extra do dicionário.
3. Confira que o cenário de teste contém o caso que a sabotagem deveria
   quebrar (o dado com o dente certo) antes de confiar num vermelho ou num
   verde.

A régua de bolso: **se a sabotagem não muda o que o usuário do código
recebe, ela não é sabotagem** — é só um comentário a mais no meio da função,
que a prova por mutação existe justamente para não deixar passar.
