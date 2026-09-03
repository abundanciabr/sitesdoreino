(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-030-a-espera-pede-pouso-sozinha-no-verde",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O pedido de pouso virou automático: ao ficar verde, o robô pede sozinho",
  detalhe: "Você passou horas esperando hoje achando que o robô esperava por "
    + "você. O que aconteceu de verdade: os PRs pousaram em minutos, mas o "
    + "rito de pouso tinha três passos separados (esperar os checks, conferir "
    + "o portão, pedir pouso), e os dois últimos dependiam de o robô voltar "
    + "para executá-los; e o relatório final não disse, com todas as letras, "
    + "que nada dependia de ninguém.\n\n"
    + "O PR #927 conserta os dois. A espera dos checks ganhou a opção de, ao "
    + "ficar verde, passar pelo mesmo portão de sempre e pedir o pouso "
    + "sozinha, num comando só. Vermelho, estouro de tempo ou medição "
    + "impossível nunca viram pedido, e o portão continua recusando por conta "
    + "própria quando falta algo (base velha, registro ausente, dívida do "
    + "livro). Cinco testes provam isso, inclusive o caso em que o portão "
    + "recusa. As regras da casa (CLAUDE.md e RITOS.md) passam a ensinar esse "
    + "comando como o caminho normal, e mandam o relatório final dizer sempre "
    + "que nada mais depende de ninguém e quanto a fila costuma levar (8 "
    + "minutos de mediana). A lição está na armadilha 300.\n\n"
    + "Mandato: ci/ e RITOS.md são caminhos protegidos; a autorização é o seu "
    + "pedido explícito de hoje ('encontre uma maneira de fazer isso "
    + "automaticamente').",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/927",
  verificado_em: null,
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
