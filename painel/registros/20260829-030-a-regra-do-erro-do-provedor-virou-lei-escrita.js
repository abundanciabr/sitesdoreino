(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-030-a-regra-do-erro-do-provedor-virou-lei-escrita",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A regra do erro do Mercado Pago virou lei escrita — a metade que o fechamento de ontem não cobriu",
  detalhe:
    "O pedido mais antigo da sua caixa, de 21/08, pedia DUAS coisas. Ontem " +
    "você tocou o rito e a primeira foi entregue: o contrato da parte do " +
    "dinheiro passou a dizer que o Mercado Pago pode falhar, e o sistema " +
    "passou a publicar essa mesma resposta. O pedido foi fechado com isso.\n\n" +
    "A SEGUNDA METADE FICOU PARA TRÁS, e é o que entra agora. O texto do " +
    "pedido dizia, com estas palavras, que 'a regra que ele protege não está " +
    "no livro de invariantes'. O livro de invariantes é onde moram as regras " +
    "que o projeto promete nunca quebrar — cada uma com um teste que fica " +
    "vermelho se alguém a desfizer. A regra do erro do provedor não estava " +
    "lá. Agora está.\n\n" +
    "O QUE A REGRA DIZ, em português: quando o Mercado Pago não responde, " +
    "responde erro, ou responde 'deu certo' com um conteúdo que não descreve " +
    "a cobrança pedida, o sistema responde 'deu erro no provedor' — nunca " +
    "finge sucesso, e nunca entrega uma tela de pagamento vazia. E quem " +
    "tentar de novo usa a MESMA senha da tentativa anterior, jamais uma " +
    "nova — senha nova seria cobrar a pessoa duas vezes.\n\n" +
    "POR QUE ISSO IMPORTA MESMO COM O CÓDIGO CERTO DESDE AGOSTO: o teste que " +
    "protege a regra já existia e já rodava. O que faltava era a regra estar " +
    "ESCRITA — sem isso, quem reescrevesse essa parte no futuro não teria " +
    "como saber que estava desfazendo uma decisão, em vez de arrumando um " +
    "detalhe.\n\n" +
    "Nada de código mudou. É só a lei alcançando o que a prática já fazia — " +
    "e o inventário de invariantes, que reprova de propósito quando um " +
    "nasce, obrigou a conferência antes de deixar passar.\n\n" +
    "NOTA DE HONESTIDADE: duas sessões trabalharam na sua caixa ao mesmo " +
    "tempo hoje. Enquanto eu escrevia esta metade, a outra fechou o pedido " +
    "com a primeira. Este registro não fecha nada — ele completa.",
  autoridade: "rito",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/472 — INVARIANTES.md ganha o [INV-P15], e ci/tests/test_guarda_dos_guardas.py passa a conhecê-lo (o inventário compara a lista COMPLETA de códigos e reprova quando um nasce, de propósito). Vermelho: run 33266475790 (muralhas do commit f3ad4e3b, o inventário reprovando). Verde: pytest ci/tests/test_guarda_dos_guardas.py, 47 passed. Teste-guarda que já existia e já rodava: services/pagamentos/tests/test_transporte_mp_fail_closed.py. Metade anterior do mesmo rito, fechada por outra sessão: registro 20260828-090 (PRs 417 e 420).",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "vender",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
