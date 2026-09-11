---
schema_version: 2
armadilha: 466
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: painel/testes/teste_logica.js
sinal:
  - estado parcial com evidência atual aparece como capítulo sem prova
  - substituir um rumo muda a quantidade ou a data dos rumos cumpridos
gatilho:
  - painel/registros/*.js
licao: prova de estado independe da cor e vence pela data de verificação. Substituição oculta o rumo antigo, mas não o cumpre nem apaga uma entrega anterior.
---

# 466: o mapa confundia prova com sucesso e substituição com entrega

O resumo contava capítulo com prova somente quando o estado era verde. Cinco
estados parciais, todos com evidência conferida, fariam a tela declarar zero
capítulos provados. A conta correta exige evidência, data de verificação e prova
ainda válida; a gravidade continua descrevendo o estado observado.

O mesmo cálculo tratava qualquer responde_a de rumo como cumprimento. Marcar uma
orientação nova como substituição podia criar uma entrega falsa ou esconder uma
entrega real anterior, conforme a ordem das respostas. O mapa pode ocultar o rumo
com qualquer resposta; o placar de confiança procura a última resposta que não
seja substituição.

O guarda separa ausência de evidência, ausência de data, prova vencida, fato antigo
reconferido, rumo apenas substituído e rumo entregue antes de uma substituição.
As armadilhas 128 e 432 cobrem, respectivamente, rumo escrito de estado velho e
alerta sem vínculo. Esta entrada cobre a semântica das contagens.
