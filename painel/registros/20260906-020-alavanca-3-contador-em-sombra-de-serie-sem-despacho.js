(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-020-alavanca-3-contador-em-sombra-de-serie-sem-despacho",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "A fabrica ganhou um contador para saber quando um pedido virou serie sem despachar robos (PR #1160)",
  detalhe: "O documento das alavancas de 10x mediu que, das 60 sessoes mais recentes, so 4 chegaram a chamar o robo despacho; o resto fez os varios PRs de um pedido um atras do outro, na mesma sessao, sem dividir o trabalho.\n\nEsta e a Alavanca 3: o gancho que ja cobra o relatorio no fim de cada tarefa (ci/prestacao_de_contas.py) passou a contar, so no caderninho de medicao e sem aparecer na tela de ninguem, quando uma sessao abriu 2 ou mais PRs sem ter chamado o robo despacho nenhuma vez. Nada muda de comportamento ainda: e so a medida, para depois decidir com numero se vale a pena cobrar isso de verdade.\n\nEsta mudanca tocou a pasta ci/, que e protegida. A autorizacao foi dada por voce nesta mesma conversa, numa pergunta estruturada, respondendo 'Sim, construir agora (recomendado)'.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1160",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
}); })();
