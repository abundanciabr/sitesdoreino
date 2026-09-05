(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-075-as-alavancas-de-10x-da-fabrica-estao-no-site",
  tipo: "entrega",
  quando: "2026-09-05",
  titulo: "A analise de onde a fabrica perde tempo, e as 5 alavancas de 10x, estao no site (so admins)",
  detalhe: "Pedido dele em 05/09. Medido em 120 PRs, 200 execucoes da esteira e 60 sessoes: o robo que escreve codigo nao e o gargalo. Achados: a conferencia do Windows (4 min 50 s) manda no relogio de todo PR sem ser exigida pela main; 155 voltas de base envelhecida para 71 PRs; a suite dos portoes roda 4 vezes por PR; so 4 de 60 sessoes despacharam robos em paralelo. As 5 alavancas, na ordem, estao em /admin/documentos/alavancas-10x-da-fabrica.",
  autoridade: "sessao",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/1119. pytest da admin: 1091 passed; mutacao da migracao 0010 reprova; muralhas: PASS.",
  verificado_em: "2026-09-05",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
