(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-039-a-armadilha-185-agora-e-pega-na-hora-do-commit",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O erro que pegou um robo 4 vezes num dia agora e recusado na hora, nao 10 minutos depois",
  detalhe: "Voce mostrou um robo que caiu 4 vezes no mesmo erro (registro escrito antes de o PR existir, sem numero) e decidiu confiar na propria disciplina. Disciplina que falha 4 vezes num dia nao e garantia. O conserto: o mesmo erro que a porta do pouso so recusava depois de uma rodada inteira de checks agora e recusado no instante do commit, na maquina, com a mensagem que reensina a ordem certa (trabalho, depois PR, depois numero, depois registro). O custo de cada tropeco cai de uns 10 minutos para 10 segundos. A porta continua conferindo tudo no fim, como sempre.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1182 (PR #1182). 43 testes verdes (13 novos); commit real sem numero foi BLOQUEADO e com numero passou; muralhas locais PASS.",
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
