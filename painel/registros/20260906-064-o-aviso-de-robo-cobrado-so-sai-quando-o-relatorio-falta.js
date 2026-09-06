(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-064-o-aviso-de-robo-cobrado-so-sai-quando-o-relatorio-falta",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O aviso de 'robô cobrado e terminou assim mesmo' só sai quando o relatório falta de verdade",
  detalhe: "Toda vez que o portão da prestação de contas recusava o fim de uma conversa, o robô escrevia o relatório e mesmo assim aparecia na sua tela o aviso de que ele tinha sido cobrado e terminado sem prestar contas. Medido nos dois dias de vida do portão: 50 avisos, e em 32 deles o relatório estava na tela.\n\nA causa: o portão tratava 'já houve uma recusa' como 'a recusa foi ignorada', sem reler a conversa. Agora ele relê com a mesma régua da primeira vez. Relatório presente: silêncio. Relatório faltando: o aviso continua, e nunca prende a conversa em laço.\n\nO que muda para você: quando esse aviso aparecer, ele passa a ser verdadeiro.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1206 (PR #1206). pytest ci/tests/test_prestacao_de_contas.py: 45 passed. O teste novo falha contra o portão da main e passa com o conserto. Muralhas locais: RESULTADO PASS (13). Armadilha 368 com gatilho no próprio portão.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
