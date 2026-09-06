(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-012-o-furo-da-vacina-do-deploy-ancestralidade-nao-e-cobertura",
  tipo: "incidente",
  quando: "2026-09-06",
  titulo: "A vacina contra deploy cancelado tem um furo: ela confere se o codigo chegou, nao se a celula subiu",
  detalhe: "Medido hoje em producao. O PR #1145 (celula mensageria) mergeou, e o deploy dele foi cancelado pela cadeira musical (o problema antigo, ja catalogado em outra armadilha). A vacina automatica acordou sozinha e decidiu NAO repetir, porque dois deploys seguintes (PRs #1146 e #1147) ja tinham o commit dela por dentro.\n\nMas nenhum dos dois deploys seguintes construiu a celula mensageria: os dois so reconstruiram a celula admin, porque nenhum dos dois PRs tocou nos arquivos da mensageria. O codigo do PR #1145 ficou fora do ar, com tres deploys verdes na tela e a propria vacina antifalso-verde dizendo que estava tudo bem.\n\nSo apareceu porque eu fui olhar, deploy por deploy, QUAIS celulas cada um de fato construiu, em vez de confiar na cor do resumo.\n\nO QUE JA FOI FEITO: catalogado como uma entrada nova de armadilha (a licao ficou escrita, com a receita de diagnostico que funciona hoje, a mao). O conserto de verdade -- ensinar a vacina a conferir CELULA, nao so commit -- foi registrado no balcao de tarefas para ser feito depois, porque mexe em arquivos que sao so seus por contrato (ci/ e .github/) e hoje nao havia autorizacao para tocar neles.\n\nO QUE ISSO SIGNIFICA NA PRATICA: enquanto o conserto nao entra, todo cancelamento de deploy exige checar a mao se a celula certa realmente subiu depois -- nao basta ver o resumo verde da vacina.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1152",
  verificado_em: "2026-09-06",
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
