// A pergunta foi do mantenedor, olhando as vigias falarem na janela: "esse
// agendamento de 15 minutos resolve algum problema concreto ou causa mais
// demora desnecessária?". Resposta medida: as duas coisas — e a parte da
// demora morreu hoje, em duas entregas de duas sessões diferentes.
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-027-a-pista-acordou-do-relogio-para-o-evento",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A pista acordou: do relógio de 15 min para o evento — pousos em ~2 min",
  detalhe:
    "A pista de pouso dormia entre passagens e só acordava a cada ~15 min — " +
    "um PR cujos testes levam 90 segundos esperava até meia hora num dia " +
    "cheio (medido hoje: 25 a 31 min). Duas entregas fecharam isso: outra " +
    "sessão fez a pista acordar quando os TESTES de qualquer PR concluem " +
    "(commit 2afa6f0), e o PR #462 " +
    "(https://github.com/abundanciabr/sitesdoreino/pull/462) fechou o buraco " +
    "que sobrava — o fluxo padrão da casa etiqueta DEPOIS dos testes verdes, " +
    "então nenhum evento vinha; agora a PRÓPRIA ETIQUETA acorda a pista, " +
    "rodando sempre a definição da main (um PR não consegue alterar o juiz " +
    "que o julga; teste-guarda tranca isso). O relógio de 15 min continua, " +
    "rebaixado a rede de segurança. Prova ao vivo: o #462 pousou em 1min31s " +
    "— o pouso mais rápido do dia, colhido pelo mecanismo que ele mesmo " +
    "completou.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/462",
  verificado_em: "2026-08-29",
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
