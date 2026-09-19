---
schema_version: 2
armadilha: 468
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: "O teste atual confere apenas fábrica na primeira posição e vender na última; trocar comunidade e curso continua verde. Este PR registra a orientação sem ampliar o produto."
sinal:
  - um plano numera capítulos pela posição em FRENTES
  - comunidade e curso recebem números diferentes dos mostrados no Meu mapa
  - ORDEM_DO_MAPA em painel/logica.js
---

# O vocabulário de frentes não numera os capítulos

`FRENTES` lista os cinco nomes aceitos pelo livro. `ORDEM_DO_MAPA` determina a
narrativa que a pessoa vê: fábrica, site, comunidade, curso e vender. Confundir
as duas listas transforma comunidade em capítulo 2 e curso em capítulo 3.

Antes de nomear um capítulo em plano, prompt ou registro, confira a constante e
a página gerada; a posição no vocabulário não é prova da numeração exibida. O
teste atual só exige fábrica primeiro e vender por último. Ele não detecta a
troca entre comunidade e curso, portanto esta orientação ainda não tem guarda
específica.
