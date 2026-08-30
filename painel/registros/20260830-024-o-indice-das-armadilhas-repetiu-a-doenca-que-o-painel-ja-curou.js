(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-024-o-indice-das-armadilhas-repetiu-a-doenca-que-o-painel-ja-curou",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "Dois robos do mesmo lote esbarraram no mesmo arquivo — e e a doenca que o painel ja curou uma vez",
  detalhe: "VOCE MANDOU 4 ROBOS TRABALHAREM AO MESMO TEMPO hoje de manha. Tres entregaram; um parou de proposito (esse esta em outro registro). Mas DOIS dos quatro tiveram o trabalho DEVOLVIDO pela esteira — e nos dois casos o motivo foi o MESMO arquivo, que nenhum dos dois tinha escrito de verdade.\n\nO QUE ACONTECEU, sem termo tecnico: existe um indice das licoes do projeto — a lista que todo robo consulta no comeco de uma tarefa para nao repetir erro velho. Esse indice nao e escrito a mao: ele e MONTADO por um programa a partir das licoes. Toda vez que um robo aprende algo e escreve uma licao nova, o indice inteiro e remontado.\n\nAi esta o problema: o indice remontado viaja junto com o trabalho. Dois robos que aprenderam coisas DIFERENTES, em cantos diferentes do projeto, entregam dois indices remontados — e o sistema nao tem como saber qual vale. Ele para e devolve os dois. Nenhum dos dois errou; eles esbarraram num arquivo que nem escreveram.\n\nHOJE ISSO CUSTOU: o PR 571 foi devolvido uma vez, e o PR 573 foi devolvido DUAS vezes (na segunda, o conflito trouxe junto um segundo arquivo montado pelo mesmo programa). Cada devolucao e uma volta inteira: remendar, esperar a medicao de novo, pedir pouso de novo.\n\nE A PARTE QUE IMPORTA: ESTA DOENCA JA FOI CURADA NESTA CASA, EM 28/08/2026. Era exatamente o mesmo filme com o painel — enquanto o painel montado viajava junto com o trabalho, dois robos no mesmo dia colidiam sem ter escrito uma linha em comum, e um trabalho de 4 arquivos levou OITO tentativas para entrar. A cura foi simples: o arquivo montado parou de viajar, e quem passou a monta-lo foi a esteira, sozinha, na hora de publicar.\n\nO indice das licoes esta hoje exatamente onde o painel estava antes da cura. A mesma receita provavelmente serve — mas tem uma diferenca que precisa ser conferida antes, e nao chutada: o indice e LIDO por gente e por robo no comeco de toda tarefa, entao tira-lo do lugar tem um custo que o painel nao tinha.\n\nVIROU TAREFA NA FILA (TAR-022), com a receita da cura anterior citada e com a ordem explicita de PARAR e devolver a analise se a diferenca inviabilizar a copia direta. Nao construi nada agora: o lote de hoje era outro, e inventar a cura no meio dele seria a pressa que este projeto ja aprendeu a nao ter.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/576 — este PR, que traz a TAR-022 e este registro. MEDIDO em 30/08/2026 durante o lote de 4 despachos: a pista devolveu o PR 571 com 'conflitos FAIL' (todos os 9 outros itens do portao PASS) e o PR 573 duas vezes pelo mesmo motivo; o comando de resolucao foi identico nas tres vezes — 'git checkout --theirs armadilhas/INDICE.md' seguido de 'python ci/indice_de_armadilhas.py', que respondeu 'PASS indice-de-armadilhas: INDICE.md regenerado(s) (175 entradas)' e, na terceira, 'INDICE.md, GUARDAS.json regenerado(s) (177 entradas)'. A cura anterior esta em armadilhas/156 e na Onda 3 de docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
