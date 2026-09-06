(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-079-o-pagamento-repassa-o-produto",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "Degrau 3: o aviso do pagamento aprovado passa a carregar o produto",
  detalhe: "Terceiro dos quatro degraus. Quando um pagamento e aprovado, no Pix ou no cartao, o aviso interno que o sistema manda passa a dizer O QUE a pessoa comprou.\n\nO PAGAMENTO NAO ENTENDE de curso, e continua nao entendendo: ele so repassa o que recebeu, do mesmo jeito que ja fazia com outros dados que nao sao dele. Isso e de proposito, para o sistema de cobranca nunca precisar saber como a escola funciona.\n\nQUANDO NAO HA PRODUTO, o campo simplesmente NAO VAI, em vez de ir vazio. Ausencia quer dizer 'nao sei'; vazio iria querer dizer 'sei que e nada', e isso nao existe.\n\nNADA DO MERCADO PAGO foi tocado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1221 (PR #1221). Suite da celula pagamentos em PostgreSQL real: 53 passed, com a main do rito #1209 dentro. ANTES do rito, o mesmo suite reprovava de proposito no teste que valida o envelope emitido contra o contrato congelado (armadilhas/243 funcionando). Prova por mutacao, tres sabotagens, cada vermelho na assercao: o pix para de ecoar, o pix manda string vazia em vez de omitir a chave, o cartao para de ecoar. black --check: 40 arquivos, nenhum a reformatar. A dependencia jsonschema ja e declarada por seis outras celulas pelo mesmo motivo.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
