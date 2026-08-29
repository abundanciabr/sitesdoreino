(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-110-o-portao-que-nao-sabia-medir-contrato-de-evento",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "Um portao do CI nao sabia medir contrato de evento — e por isso editar um era impossivel",
  detalhe: "ISTO APARECEU NO CAMINHO DE CONSTRUIR O AVISO DE LIBERACAO, e vale por si.\n\nO projeto tem uma regra: acrescentar num contrato e livre, tirar exige autorizacao. Quem faz ela valer e um portao do CI. So que esse portao esperava um formato so — o dos contratos de API — e travava, fechado, em qualquer arquivo de outro formato. Os contratos de EVENTO (as 'cartas' que uma parte do sistema manda para outra) sao de outro formato.\n\nRESULTADO: editar uma carta que ja existe era IMPOSSIVEL. O portao nem chegava a comparar; ele parava dizendo 'nao reconheco este formato'.\n\nNINGUEM TINHA NOTADO em nenhum momento da historia do projeto, e a razao e boa: ate hoje, toda carta nova nasceu como ARQUIVO novo. Arquivo novo e adicao pura, e nem passa pela comparacao. A regra 'acrescentar e livre' valia so para metade dos contratos, por acidente — e o dia em que ela precisou valer para a outra metade foi o dia em que o buraco apareceu.\n\nAGORA O PORTAO SABE LER AS DUAS FORMAS. Para as cartas, ele mede as tres coisas que quebram quem ja as recebe: um campo que some, um campo que passa a ser obrigatorio, e um valor de lista que desaparece. Esse ultimo e o mais caro dos tres, porque so aparece em producao — na primeira carta do tipo antigo que alguem ainda manda.\n\nNAO PRECISOU NASCER EM SOMBRA, e a razao e mecanica e nao de confianca: ANTES, toda edicao de carta travava o PR. Agora, a aditiva passa e a que quebra reprova. Nao existe nenhum caso que passava e agora reprova — o portao so ficou capaz de olhar para onde antes se recusava a olhar.",
  autoridade: "github",
  evidencia: "PR #523. Vermelho->verde MEDIDO: os 11 guardas novos nem importam sem a mudanca (as funcoes e_evento e quebras_de_evento nao existem em ci/contrato_aditivo.py na main de antes). Com ela: 33 passed em ci/tests/test_contrato_aditivo.py e 1037 passed em ci/tests inteiro. Entre os guardas novos esta test_evento_editado_no_repo_passa_pelo_portao_de_ponta_a_ponta, que monta um repositorio de mentira, edita uma carta e roda o portao INTEIRO — esse cenario terminava em ERROR antes deste PR, e e a prova de que o bloqueio era real e nao teorico. TOCA ci/ (CODEOWNERS), anunciado nominalmente ao mantenedor.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
