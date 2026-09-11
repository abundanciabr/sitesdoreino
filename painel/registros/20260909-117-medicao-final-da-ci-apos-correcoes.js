(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260909-117-medicao-final-da-ci-apos-correcoes",
  tipo: "nota",
  quando: "2026-09-09",
  titulo: "Medição final da CI após correções",
  detalhe: "Os guardas do painel, do Make e do Bash passaram. A suíte adversarial passou com 2378 testes e 11 ignorados. O freeze completo ainda tem erro em células que exigem versões incompatíveis no mesmo virtualenv local.",
  autoridade: "sessao",
  evidencia: "ci.py --apenas muralhas,guardas: RESULTADO PASS. pytest test_exit_do_make.py test_suite_em_paralelo.py: 25 passed. ci.py com ambiente oficial: testar-o-testador PASS, 2378 passed, 11 skipped; contratos incompatíveis permanecem ERROR.",
  verificado_em: "2026-09-09",
  precisa_do_dono: true,
  responde_a: "20260909-084-guardas-do-staging-do-admin-atualizados",
  gravidade: "ambar",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,
  se_eu_nao_decidir: "O freeze completo local continua sem veredito para as células com requirements incompatíveis.",
  recomendacao: "Executar cada célula em ambiente isolado, como no workflow oficial, antes de usar o freeze completo como PASS.",
  reversivel: true
}); })();
