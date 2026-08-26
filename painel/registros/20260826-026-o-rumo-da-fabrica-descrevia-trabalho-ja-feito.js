(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-026-o-rumo-da-fabrica-descrevia-trabalho-ja-feito",
  tipo: "nota",
  quando: "2026-08-26",
  titulo: "As três peças da fábrica que eu ia construir hoje já estavam prontas desde ontem",
  detalhe: "Antes de despachar, fui conferir no código o que o rumo da fábrica dizia faltar — o vigia dos vigias, o alarme completo da linha principal e a partida em 1 comando. As três estão no ar desde 25/08/2026, entregues nos PRs #173, #171 e #174.\n\nInclusive conferi a única dúvida que sobrou: o vigia dos vigias parecia não rodar na esteira automática. Roda — por dentro da suíte que os dois portões já executam, e o próprio arquivo explica isso. Não há buraco.\n\nPOR QUE O RUMO ESTAVA ERRADO: ele foi escrito a partir de uma fotografia de painel antiga, e a fotografia se contradizia — uma seção dizia 'faltam 3 peças' e outra, no mesmo arquivo, listava as três como entregues. Quem leu de cima para baixo escreveu o rumo de boa-fé.\n\nO QUE ISSO CUSTOU E O QUE EVITOU: custou alguns minutos de medição. Evitou gastar um lote inteiro refazendo trabalho pronto. A lição virou regra escrita para as próximas sessões (armadilhas/128): rumo é o único tipo de registro que afirma uma AUSÊNCIA, e ausência não se lê em documento — se mede no código.\n\nNada a fazer nesta frente. Ela está em dia.",
  autoridade: "sessao",
  evidencia: "PRs #171, #173 e #174 mergeados em 25/08/2026; ci/guarda_dos_guardas.py em disco, invocado por ci/tests/test_guarda_dos_guardas.py, que roda em `muralhas` e `alarme-main`; alarme-main.yml declara por escrito o skip medido das duas muralhas de diff",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-010-rumo-fabrica-tres-pecas",
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
