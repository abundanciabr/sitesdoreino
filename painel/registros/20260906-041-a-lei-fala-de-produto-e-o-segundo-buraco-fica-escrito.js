(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-041-a-lei-fala-de-produto-e-o-segundo-buraco-fica-escrito",
  tipo: "decisao",
  quando: "2026-09-06",
  titulo: "A lei passa a falar de PRODUTO, e o segundo buraco fica escrito",
  detalhe: "Emenda sua, com as suas palavras: o aluno esta matriculado em algum curso, ou comprou algum produto, mas sempre entra pela via da compra de algo. A lei de ontem falava so de CURSO; agora fala de PRODUTO, e curso e um produto entre outros. Um livro em PDF cabe na mesma regra sem uma linha a mais, e o campo no sistema ja se chamava product_id.\n\nA CORRECAO QUE VOCE APONTOU: eu tinha escrito na lei que quem compra ja informa o curso. Era falso. Quem mediu o caminho de verdade foi o robo da TAR-220: o aviso da compra (pagamento.aprovado.v1) carrega pagamento, pedido, valor e cliente, e NENHUM produto. Quem paga hoje vira aluno ativo sem produto nenhum.\n\nENTAO SAO DOIS BURACOS, nao um. O da sala de espera fecha com a TAR-220 (a tela de liberar passa a exigir escolher). O da compra e a TAR-225, e e o mais grave: e a porta principal, por onde entra quem paga.\n\nO erro ficou escrito na lei de proposito, com a licao: assinatura de funcao nao e caminho de dado.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1181 (PR #1181), com a emenda em docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md e a tarefa TAR-225 na fila. Medido no contrato congelado contracts/eventos/pagamento.aprovado.v1.json: os campos de data sao site_id, payment_id, order_id, amount_cents, method, mp_payment_id e customer. Muralha do travessao: 0 travessoes no arquivo.",
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
