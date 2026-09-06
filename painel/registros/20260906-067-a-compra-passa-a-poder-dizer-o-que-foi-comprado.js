(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-067-a-compra-passa-a-poder-dizer-o-que-foi-comprado",
  tipo: "decisao",
  quando: "2026-09-06",
  titulo: "Cerimonia do contrato: a compra passa a poder dizer o que foi comprado",
  detalhe: "Voce mandou fechar isso hoje, e este e o primeiro degrau. Ate agora, quando alguem pagava, o aviso interno que o site manda dizia o pagamento, o pedido, o valor e o cliente, e NAO dizia o que a pessoa comprou. Por isso quem pagava virava aluno sem curso nenhum, calado.\n\nO QUE MUDOU: o aviso ganhou um campo para o produto. Ele e opcional de proposito, para nada do que ja existe quebrar, e quando nao ha produto o campo simplesmente NAO VEM, em vez de vir vazio: ausencia quer dizer 'nao sei', e vazio iria querer dizer 'sei que e nada', que nao existe.\n\nEU NAO ENCOSTEI NO MERCADO PAGO nem na tela de compra, como combinamos. O que muda e so o dado que viaja junto.\n\nFALTAM TRES DEGRAUS, todos ja medidos: a tela de compra guardar o produto, o pagamento repassa-lo, e a matricula grava-lo.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1209 (PR #1209), com a etiqueta contrato. Com o congelado e o codigo na mesma arvore, uma vez, antes de separar (armadilhas/243 passo 2): suite da celula pagamentos 53 passed em PostgreSQL real. Sem o contrato, a mesma suite reprova de proposito no teste que valida o envelope emitido contra o congelado. Regra aditiva: PASS, nada removido, e product_id nao entrou no required.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
