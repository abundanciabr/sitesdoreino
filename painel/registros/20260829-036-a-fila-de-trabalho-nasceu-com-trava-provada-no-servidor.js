// Fase 2 do plano da lista de tarefas (registro 032; veredito no PR 511).
// O degrau que os três consultores apontaram como o obstáculo real: a
// fonte. Este registro viaja no próprio PR da entrega (515) — painel/
// e ci/fila são a mesma frente, célula admin + caminhos sem célula.
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-036-a-fila-de-trabalho-nasceu-com-trava-provada-no-servidor",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A fila de trabalho nasceu — e a trava contra dois robôs na mesma tarefa foi provada ao vivo",
  detalhe:
    "Tarefa agora é coisa registrada, não lembrança de sessão. A pasta " +
    "fila/ guarda um arquivo por tarefa e um por acontecimento, no mesmo " +
    "molde do livro: nada se edita, corrigir é acrescentar, e o estado de " +
    "cada tarefa (na fila, reivindicada, em execução, bloqueada, " +
    "concluída) é sempre CALCULADO — não existe campo de status para " +
    "alguém esquecer de atualizar ou mentir.\n\n" +
    "A TRAVA: quando um robô pega uma tarefa, quem arbitra é o servidor " +
    "do GitHub — o segundo a chegar é recusado NA HORA, e a reserva " +
    "expira sozinha em 3 horas se a sessão morrer. Foi provado ao vivo " +
    "hoje: duas sessões disputaram a mesma tarefa e a segunda levou a " +
    "recusa do servidor, com a saída crua colada no PR.\n\n" +
    "CONCLUIR EXIGE PROVA: fechar tarefa sem evidência é recusado pelo " +
    "balcão — a mesma lei do verde deste livro. E uma muralha nova " +
    "confere a fila inteira em todo PR.\n\n" +
    "A fila já nasce com as duas próximas etapas do plano dentro dela: " +
    "TAR-001 (semear as tarefas reais e escrever a lei no RITOS) e " +
    "TAR-002 (a aba \"Os robôs\" — que o quadro já mostra como bloqueada " +
    "esperando a TAR-001, calculado por conta própria).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/515",
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
