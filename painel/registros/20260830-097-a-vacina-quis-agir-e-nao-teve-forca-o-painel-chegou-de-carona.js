(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-097-a-vacina-quis-agir-e-nao-teve-forca-o-painel-chegou-de-carona",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A vacina do deploy quis agir e não teve força; o painel foi atualizado de carona",
  detalhe: "O robô-enfermeiro que reergue deploys cancelados acordou na hora certa e tomou a decisão certa sobre o deploy cancelado do PR 657 — mas, na hora de apertar o botão de repetir, o crachá dele não abriu essa porta (faltou uma permissão). O alarme automático funcionou e anotou o caso na issue 651. Um redisparo feito à mão nesta sessão também foi cancelado pela mesma disputa de vaga entre deploys — parou-se na segunda tentativa, como manda a regra.\n\nNão ficou estrago: dois minutos depois, a entrega seguinte (PR 658) reconstruiu a mesma parte do painel já com tudo dentro, e foi conferido de verdade — pelo histórico do Git — que esse deploy verde carregava o conteúdo do PR 657. O painel está atualizado no ar.\n\nPara dar força ao robô-enfermeiro de uma vez, nasceu a tarefa TAR-051 no balcão da fila, registrada junto com esta anotação (PR 663). Ela manda medir se basta uma permissão no próprio robô ou se precisa de uma chave que só você cria — e, nesse caso, a pergunta virá a você do jeito combinado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/663 · deploy verde que cobriu a célula: https://github.com/abundanciabr/sitesdoreino/actions/runs/33341602800",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
