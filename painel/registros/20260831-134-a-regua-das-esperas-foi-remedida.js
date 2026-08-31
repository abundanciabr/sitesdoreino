(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-134-a-regua-das-esperas-foi-remedida",
  tipo: "medicao",
  quando: "2026-08-31",
  titulo: "A régua que diz quanto cada espera demora foi remedida, e uma fonte errada foi tapada",
  detalhe: "Quando um robô fica esperando alguma coisa (um teste, um deploy, a vez do PR na fila), ele avisa na tela quanto aquilo costuma levar: \"normalmente isso leva uns 2 minutos\". Esse \"costuma levar\" sai de uma tabela de tempos medidos, e a tabela estava com dois números de dois dias atrás que já não batiam com a realidade.\n\nO pior era a espera da fila de merge: a tabela tinha só 5 casos medidos, e com tão pouca coisa o robô era obrigado a dizer \"olha, tenho pouca amostra, desconfie de mim\". Agora são 233 casos, todos dos últimos três dias, e o número mudou bastante: o que estava anotado como 7 minutos é, na verdade, 1 minuto e 49 segundos.\n\nO outro número errado fazia o robô dar alarme falso. O deploy estava anotado como mais rápido do que realmente é, então um deploy perfeitamente normal disparava um aviso de \"isso está demorando mais do que o esperado\". Com a medição de hoje, o deploy normal voltou a ser normal.\n\nNo meio do trabalho apareceu um defeito que valia mais que a própria atualização. O programa que recalcula os tempos sozinho iria gravar que \"o Docker acorda em 2 segundos\", quando o número real medido à mão é 90 segundos. Ele estava misturando esperas que não têm nada a ver umas com as outras: qualquer espera solta caía no mesmo balde do Docker, e o balde tinha um monte de esperas curtas de outra natureza. Nada apitava, porque uma tabela errada não quebra nada na hora, ela só faz o robô mentir baixinho, com cara de quem mediu.\n\nO conserto foi fazer cada espera anotar a que balde ela pertence. Quando não houver nenhuma espera do tipo certo, o programa agora deixa o número antigo em paz e escreve na tela que não teve amostra nova, em vez de inventar. Isso ficou registrado na memória de campo do projeto como a armadilha 259.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/808",
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
