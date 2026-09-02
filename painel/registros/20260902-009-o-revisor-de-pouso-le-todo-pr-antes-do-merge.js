(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-009-o-revisor-de-pouso-le-todo-pr-antes-do-merge",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "Agora um robô revisor lê todo trabalho antes de ele entrar, e escreve o que achou",
  detalhe: "Até hoje, quando um robô terminava uma tarefa, ninguém lia o trabalho dele. As conferências automáticas diziam apenas \"passou\" ou \"não passou\" — e existe um tipo de erro que passa por elas sem ser visto.\n\nO erro é este: o teste que deveria vigiar uma regra fica verde MESMO com a regra apagada do programa. Ele não vigia nada, mas parece que vigia. No dia 01/09 isso apareceu SEIS vezes, sempre porque a conferência tinha mais de um motivo possível para dar certo, e o motivo certo não era o que estava sendo medido. Nenhuma das seis foi pega por máquina: todas por um robô quebrando o próprio programa de propósito para ver se o teste reclamava.\n\nO que entra agora: no momento em que um trabalho vai ser incorporado, um revisor com olhar novo lê tudo que mudou e escreve um recado no lugar onde o trabalho mora. Ele aponta quatro coisas, e nenhuma delas é do tipo que as máquinas já apontam. A principal é justamente essa: \"esta conferência tinha mais de um jeito de dar certo, você conferiu qual?\".\n\nDuas decisões importantes, e são de propósito:\n\nELE OPINA, MAS NÃO BARRA NADA. O trabalho entra do mesmo jeito. Um revisor que barra vira um porteiro sem recurso, num lugar onde não há ninguém para desempatar — e a casa já pagou caro por isso antes. Se um dia ele passar a barrar, essa é uma decisão sua.\n\nELE NÃO CONSEGUE TRAVAR A ESTEIRA. Ele mora dentro da máquina que faz todo trabalho entrar; um defeito ali não estraga uma tela, para a casa inteira. Então se ele falhar, demorar ou sumir, o trabalho entra normalmente e ele apenas diz \"não consegui revisar\" — o que já foi conferido em teste, nos três casos.\n\nCusto: pouco mais de um segundo por trabalho.\n\nA prova de que ele funciona veio de fora: rodado contra trabalhos reais que já entraram, ele apontou 6 problemas justamente naquele em que um dos seis erros de ontem foi descoberto, e 3 em outro. E, ao ser testado, achou dois defeitos nele mesmo, que foram consertados antes de entrar.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/849",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  custo: null
}); })();
