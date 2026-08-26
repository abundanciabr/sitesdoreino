(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-029-duas-celulas-de-dinheiro-ficaram-de-fora-do-fuso",
  tipo: "pendencia",
  quando: "2026-08-26",
  titulo: "Duas peças de dinheiro ficaram sem a correção da hora — parei por causa da sua ordem, e quero sua palavra",
  detalhe: "A CORREÇÃO DE HOJE cobriu três das cinco peças que faltavam. As duas que sobraram são a do carrinho (checkout) e a do pagamento.\n\nPOR QUE PAREI: você deu uma ordem clara — pagamento por último, não mexer nessas duas até você dizer que o site vai vender. Eu poderia argumentar que uma linha de configuração de fuso horário não é 'mexer em pagamento': ela não toca preço, não toca cobrança, não toca o Mercado Pago. Mas ordem sua eu não reinterpreto sozinho. Prefiro perguntar.\n\nO QUE EU FARIA, SE VOCÊ AUTORIZAR: exatamente o mesmo que fiz nas outras três — uma linha de configuração e um teste que reprova se alguém a apagar. Dois PRs pequenos, nenhuma lógica de dinheiro tocada, nenhuma tela mudada.\n\nO RISCO DE DEIXAR COMO ESTÁ: baixo hoje, e é honesto dizer por quê — nenhuma dessas duas peças mostra data na tela. O defeito fica dormindo. Ele acorda no dia em que uma tela de compra ou de recibo mostrar um horário, e aí mostra cinco horas atrás.\n\nBASTA RESPONDER 'pode corrigir as duas' numa sessão qualquer. Se preferir deixar para quando o pagamento for retomado, também está certo — fica registrado aqui e não se perde.",
  autoridade: "sessao",
  evidencia: "ARMADILHAS-OPERACAO.md §9 — a dívida do fuso, agora com duas células em aberto; armadilhas/099 traz a receita completa, a mesma aplicada nos PRs #233, #234 e #235",
  verificado_em: "2026-08-26",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "vender",
  vence_em_dias: null
});})();
