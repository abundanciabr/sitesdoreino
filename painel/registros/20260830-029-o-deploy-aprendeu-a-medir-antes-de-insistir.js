// TAR-013 — a vacina da armadilha 127, a campeã de reincidência do catálogo.
// O deploy já repetia com pausa desde 26/08; o que faltava era MEDIR e
// REGISTRAR. Evidência: PR 584.
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-029-o-deploy-aprendeu-a-medir-antes-de-insistir",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A entrega do site aprendeu a conferir se o servidor está atendendo antes de insistir",
  detalhe:
    "A falha que mais se repetiu na história deste projeto é o momento em " +
    "que a entrega do site tenta falar com o seu servidor e a conexão dá um " +
    "soluço — seis quedas em três dias. O servidor está vivo, o site fica no " +
    "ar o tempo todo; é só a linha entre o robô e o servidor que engasga.\n\n" +
    "Desde 26/08 a entrega já tentava três vezes, com pausa entre elas. Mas " +
    "ela tentava de olhos fechados: não tinha como saber se aquilo era um " +
    "soluço passageiro (em que insistir resolve) ou uma porta realmente " +
    "fechada (em que insistir é perder tempo). Agora ela CONFERE — bate na " +
    "porta do servidor antes de começar e de novo depois de cada recusa — e " +
    "usa o que descobriu: soluço passageiro, insiste; porta fechada " +
    "confirmada duas vezes, para de tentar e diz que o conserto é de " +
    "configuração e passa por você. Se não conseguir conferir, ela não " +
    "inventa: continua tentando como antes.\n\n" +
    "E ela passou a CONTAR o que fez. Até hoje, uma entrega que se salvou na " +
    "segunda tentativa era indistinguível de uma que passou de primeira — o " +
    "problema ficava invisível justamente nos dias em que mais aconteceu. " +
    "Agora a página da execução abre com o resumo em português: quantas " +
    "tentativas foram precisas, o que cada conferência viu, se o site ficou " +
    "no ar, e a frase que mais se esquece — se o que foi entregue está ou " +
    "não em produção.\n\n" +
    "O que este trabalho NÃO provou, dito na lata: não existe ainda uma " +
    "execução real em que a entrega tenha sobrevivido a um soluço. Soluço de " +
    "rede não se provoca com honestidade, e forjar um provaria outra coisa. " +
    "A conferência de partida e o resumo rodam em toda entrega a partir de " +
    "agora; as outras peças só aparecem quando o servidor recusar de " +
    "verdade — e aí a própria execução escreve a prova.\n\n" +
    "Também ficou registrado que a entrega da INFRAESTRUTURA (a parte que " +
    "arruma os canos, não as páginas) continua sem essa proteção: ela fala " +
    "com o servidor uma vez só. Virou tarefa na fila, com o roteiro pronto, " +
    "em vez de ficar na memória de uma conversa.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/584",
  verificado_em: "2026-08-30",
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
