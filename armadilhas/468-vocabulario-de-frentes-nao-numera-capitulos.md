---
schema_version: 2
armadilha: 468
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: painel/testes/teste_logica.js
sinal:
  - um plano numera capítulos pela posição em FRENTES
  - comunidade e curso recebem números diferentes dos mostrados no Meu mapa
  - ORDEM_DO_MAPA em painel/logica.js
gatilho:
  - painel/testes/teste_logica.js
licao: Para numerar capítulos, leia ORDEM_DO_MAPA e confirme a ordem mostrada na página. FRENTES valida nomes; sua posição não define a narrativa.
---

# O vocabulário de frentes não numera os capítulos

`FRENTES` lista os cinco nomes aceitos pelo livro. `ORDEM_DO_MAPA` determina a
narrativa que a pessoa vê: fábrica, site, comunidade, curso e vender. Confundir
as duas listas transforma comunidade em capítulo 2 e curso em capítulo 3.

O teste do mapa já guarda a ordem narrativa. Antes de nomear um capítulo em
plano, prompt ou registro, confira a constante e a página gerada; a posição no
vocabulário não é prova da numeração exibida.
