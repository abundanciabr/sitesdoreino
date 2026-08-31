(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-128-o-robo-parava-de-trabalhar-para-olhar-a-fila",
  tipo: "nota",
  quando: "2026-08-31",
  titulo: "O monte de 'Aguardando' era o robô parado olhando uma fila que anda sozinha (PR #801)",
  detalhe: "Você perguntou por que toda tarefa enche a tela de 'Aguardando' e por que algumas parecem levar horas. Medi os 40 PRs do dia antes de responder, e a primeira explicação que eu tinha dado (a fila estaria cheia de robôs) estava ERRADA: a fila entrega em 8,4 minutos na mediana, cada passagem dela leva 34 segundos, e ela roda 326 vezes por hora. Nada demorou horas; o pior do dia levou 34 minutos. A causa real era outra: o robô ficava PARADO esperando a fila chamar o PR dele, coisa que a lei da casa já proibia desde 29/08 ('a melhor espera é a que não acontece'). Só que a regra existia apenas no texto, e a ferramenta continuava oferecendo o caminho errado ao lado do certo. De uns 12 minutos de espera por tarefa, 8,4 eram tempo morto. Agora a ferramenta RECUSA esperar a fila e ensina o caminho no lugar, o robô segue trabalhando enquanto o deploy roda, e ele para de repetir 'Aguardando' a cada batimento. O que continua igual: o veredito do deploy ainda é conferido antes de qualquer 'está no ar', que é a trava contra falso-verde.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/801",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
