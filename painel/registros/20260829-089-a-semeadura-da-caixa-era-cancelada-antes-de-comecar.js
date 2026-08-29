(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-089-a-semeadura-da-caixa-era-cancelada-antes-de-comecar",
  tipo: "incidente",
  quando: "2026-08-29",
  titulo: "Uma tarefa nova era cancelada antes de começar — e o motivo era uma linha copiada por analogia",
  detalhe: "A primeira execução real da tarefa que semeia a Caixa foi CANCELADA em 31 segundos, sem rodar um passo sequer e sem deixar log. Não foi o script, nem a VPS, nem a chave de acesso.\n\nFoi uma linha de configuração escrita por analogia com outra tarefa, sem perguntar o que a analogia significava ali: ela colocava a tarefa nova no mesmo 'grupo de fila' das entregas automáticas. Quem entra nesse grupo é cancelado quando outra entrega começa — e foi exatamente o que aconteceu.\n\nO conserto tirou a tarefa desse grupo. Fica a lição: copiar configuração por semelhança pode importar junto um comportamento que ninguém pediu, e o sintoma não parece defeito de configuração — parece que a máquina simplesmente não fez nada.\n\nEste registro paga uma dívida do livro: a entrega foi mergeada e ninguém tinha contado a você.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/482",
  verificado_em: "2026-08-29",
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
