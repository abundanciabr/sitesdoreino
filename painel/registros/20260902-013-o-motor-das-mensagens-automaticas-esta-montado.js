(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-013-o-motor-das-mensagens-automaticas-esta-montado",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O motor das mensagens automáticas está montado: ele sabe esperar, e sabe desistir",
  detalhe: "Quarto degrau, e é o coração da coisa. A plataforma passou a saber fazer três coisas que ela nunca soube fazer: ESPERAR (\"daqui a dois dias, mande isto\"), PERCEBER que a situação mudou, e DESISTIR na hora certa.\n\nA parte de desistir é a que mais importa para o aluno. Se a sequência é \"você ainda não entrou em nenhuma aula\" e a pessoa entra numa aula no dia seguinte, a mensagem NÃO sai. A pergunta é refeita no instante do envio, nunca no da inscrição. Uma sequência que não sabe desistir manda \"senti sua falta\" para quem voltou ontem, e é isso que faz o aluno desligar tudo.\n\nE o relógio da sequência é ancorado no dia em que a pessoa entrou. Se a régua atrasou a segunda mensagem em um dia, a terceira NÃO anda junto: ela sai na data que sempre foi a dela. Sem essa regra escrita, o comportamento seria decidido por acaso e daria um problema impossível de reproduzir depois.\n\nUma decisão que eu precisei tomar e quero deixar registrada, porque ela é sobre honestidade: neste degrau a régua libera a mensagem e ainda não existe ninguém para entregá-la (a entrega no sininho é o próximo degrau). Marcar como \"enviada\" algo que não saiu seria mentira gravada no banco, e ela contaminaria até a contagem de quantas mensagens a pessoa recebeu no dia. Então o motor não marca nada: ele conta quantas ficaram esperando e devolve esse número. Quando o próximo degrau chegar, ele encaixa e nada mais muda aqui.\n\nProva: 85 testes verdes na célula (eram 68). Cinco garantias quebradas de propósito, uma por vez, e cinco vermelhos honestos.\n\nUm erro meu que rendeu aprendizado: um dos testes falhou e a leitura óbvia era \"o desempate está quebrado\". Não estava. Quem perdeu a vaga foi a linha que EU tinha chamado de vencedora, porque o cenário não dizia qual era a mais antiga, herdava isso da ordem em que eu havia escrito as instruções.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/854",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
