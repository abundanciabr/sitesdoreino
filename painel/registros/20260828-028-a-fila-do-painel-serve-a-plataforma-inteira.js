(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-028-a-fila-do-painel-serve-a-plataforma-inteira",
  tipo: "decisao",
  quando: "2026-08-28",
  titulo: "A fila do painel mostra TODAS as escolas, e nao uma so — decisao sua, no meio do lote",
  detalhe: "Registro que ficou faltando do lote de ontem a noite, e o livro cobrou: um pedaco entrou na main sem ninguem te contar. Aqui esta.\n\nO QUE FOI DECIDIDO: quando eu fui montar a tela da fila, esbarrei numa exigencia tecnica — a lista de quem esta esperando pedia que eu dissesse DE QUAL ESCOLA, e o painel nao tinha como saber. Te apresentei as duas saidas e voce escolheu: a tela mostra todo mundo que esta esperando, dizendo de qual escola cada pessoa veio.\n\nPOR QUE ISSO IMPORTA MESMO SO EXISTINDO UMA ESCOLA HOJE: o painel e da PLATAFORMA, nao de uma loja. A alternativa era eu descobrir e gravar no servidor o codigo interno da escola atual — e no dia em que existisse a segunda, a fila dela ficaria invisivel ate alguem lembrar de mexer. Voce preferiu que ela aparecesse sozinha.\n\nDETALHE DE TELA: enquanto houver so uma escola, o codigo dela NAO aparece na lista. Seria um monte de letras sem sentido no meio dos nomes. Ele so aparece quando houver mais de uma, que e quando serve para alguma coisa.\n\nISSO EXIGIU ABRIR PELA SEGUNDA VEZ, no mesmo dia, o documento congelado da parte de alunos — com a sua autorizacao nominal, como manda o rito.",
  autoridade: "mantenedor",
  evidencia: "PRs https://github.com/abundanciabr/sitesdoreino/pull/351 (o contrato, sozinho, com a etiqueta 'contrato') e https://github.com/abundanciabr/sitesdoreino/pull/353 (a implementacao). Decidido por caixa de multipla escolha em 28/08/2026, com as duas opcoes na mesa e a consequencia de cada uma escrita. Provas por mutacao no provedor: filtrar pela escola quando NENHUMA foi pedida (o erro classico, que devolveria lista vazia — 'ninguem esperando' para quem tem gente esperando) = 3 vermelhos; tirar a escola da resposta = 3 vermelhos. Um teste antigo que exigia o comportamento anterior foi REAPONTADO e nao apagado: ele agora afirma a regra nova e continua tendo dentes para os dois erros possiveis.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null
});})();
