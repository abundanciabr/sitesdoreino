(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-108-a-licao-que-a-retomada-deixou-escrita",
  tipo: "nota",
  quando: "2026-08-31",
  titulo: "A licao do cracha ficou escrita no catalogo da casa, para nao acontecer de novo",
  detalhe: "Toda vez que um robo termina uma tarefa aqui, ele e obrigado a escrever o que aprendeu num catalogo que os proximos leem antes de comecar. Esta e a entrada de hoje, e ela e a mais util que eu escrevi nesta jornada, porque nao e sobre a gamificacao: e sobre uma armadilha que qualquer parte do sistema pode cair.\n\nO RESUMO: quando uma parte do sistema avisa a outra que algo aconteceu, ela manda junto um numero que identifica a pessoa. Mas existem DOIS numeros para a mesma pessoa: o cracha interno de quem avisa, e o cracha geral da plataforma. Quem recebe e usa o cracha errado nao recebe erro nenhum: ele cria uma pessoa nova, do nada, e credita ela. O ledger enche, os testes passam, e a tela de quem trabalhou marca zero para sempre.\n\nA PARTE QUE EU ACHO MAIS IMPORTANTE, e por isso ela virou entrada: o proprio arquivo de teste ja tinha um aviso escrito no topo dizendo, com essas palavras, que um teste com aviso de fantasia prova que o motor funciona com dados que nunca vao chegar. O aviso estava la, escrito, e mesmo assim nao impediu. Aviso escrito nao e mecanismo. O que impede e comparar o formato do teste com o contrato congelado, e isso ninguem estava fazendo.\n\nA regra de bolso que ficou, e que serve para qualquer robo daqui em diante: antes de creditar ou endereçar alguem a partir de um aviso de outra parte do sistema, leia a DESCRICAO do campo no contrato, nao o nome dele. Se a descricao disser 'dentro da celula tal', aquele numero nao vale fora dela.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/783, armadilha 255. Numero pedido ao almoxarife (ci/reservar.py numero armadilha), nao escolhido a mao. ci/indice_de_armadilhas.py PASS com 229 entradas; ci/muralha-do-indice.sh reconstruiu o indice byte a byte e confirmou que os tres arquivos gerados continuam fora do Git; ci/tests/test_guarda_declarada_e_sino.py 30 passed, o que prova que os sinais novos desta entrada NAO casam com saida normal do dia a dia (era a licao das TAR-038 e TAR-043, em que um sino tocava em cima de mensagem de sucesso e ensinava todo robo a ignora-lo).",
  verificado_em: "2026-08-31",
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
