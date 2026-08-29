(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-028-a-regra-do-erro-do-provedor-virou-lei-escrita",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "Fechado: a regra do erro do Mercado Pago agora está escrita no livro de leis do projeto",
  detalhe:
    "Este era o pedido mais antigo da sua caixa — de 21/08. Ele pedia DUAS " +
    "coisas, e você só tinha sido avisado da primeira.\n\n" +
    "A PRIMEIRA (já estava feita, ontem): o contrato da parte do dinheiro " +
    "passou a dizer que o Mercado Pago pode falhar, e o sistema passou a " +
    "publicar essa mesma resposta. Foram os dois PRs do rito de contrato, com " +
    "você presente.\n\n" +
    "A SEGUNDA (é o que entrou agora): o pedido dizia, com estas palavras, que " +
    "'a regra que ele protege não está no livro de invariantes'. O livro de " +
    "invariantes é onde moram as regras que o projeto promete nunca quebrar — " +
    "cada uma com um teste que fica vermelho se alguém a desfizer. A regra do " +
    "erro do provedor não estava lá. Agora está.\n\n" +
    "O QUE A REGRA DIZ, em português: quando o Mercado Pago não responde, " +
    "responde erro, ou responde 'deu certo' com um conteúdo que não descreve a " +
    "cobrança pedida, o sistema responde 'deu erro no provedor' — nunca finge " +
    "sucesso, e nunca entrega uma tela de pagamento vazia. E quem tentar de " +
    "novo tem de usar a MESMA senha da tentativa anterior, jamais uma nova — " +
    "senha nova seria cobrar a pessoa duas vezes.\n\n" +
    "POR QUE ISSO IMPORTA MESMO ESTANDO O CÓDIGO CERTO DESDE AGOSTO: o teste " +
    "que protege a regra já existia e já rodava. O que faltava era a regra " +
    "estar ESCRITA — sem isso, alguém que reescrevesse essa parte no futuro " +
    "não teria como saber que estava desfazendo uma decisão, em vez de " +
    "arrumando um detalhe.\n\n" +
    "Nada de código mudou nesta entrega. É só a lei alcançando o que a " +
    "prática já fazia.",
  autoridade: "rito",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/472 — INVARIANTES.md ganha o [INV-P15]. Teste-guarda que já existia e já rodava: services/pagamentos/tests/test_transporte_mp_fail_closed.py (mocka no HTTP, não no método do cliente). As duas metades anteriores do mesmo rito: PRs 417 e 420, ambos MERGED.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: "20260821-001-h7-rito-de-contrato-do-502",
  gravidade: "verde",
  frente: "vender",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
