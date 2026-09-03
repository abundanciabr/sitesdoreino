(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-004-a-entrega-passou-a-repetir-o-engasgo-de-rede-sozinha",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "A entrega passou a repetir sozinha o engasgo de rede, como você pediu",
  detalhe: "VOCÊ ESCOLHEU ISTO hoje, sabendo do risco que eu apontei: repetição automática também esconde falha de verdade, e aí um problema sério vira só \"demorou um pouco mais\". Este trabalho é a versão que RESPONDE a esse risco em vez de fingir que ele não existe.\n\nO QUE MUDA NA PRÁTICA: quando o envio da imagem para o depósito engasgar, a entrega tenta de novo sozinha, até três vezes, com pausa entre elas. Você não precisa mais me pedir para repetir.\n\nA REGRA QUE IMPEDE ISSO DE VIRAR UM PROBLEMA, e ela é a parte que interessa. A repetição sabe distinguir duas coisas que parecem iguais no log:\n\n1. O depósito RESPONDEU \"não\" (senha errada, permissão faltando, endereço que não existe). Isso é um diagnóstico, e nenhuma repetição conserta. Para na primeira tentativa e mostra a mensagem.\n\n2. O depósito ficou em SILÊNCIO, ou tossiu. É o caso de hoje. Aí repete.\n\n3. E o terceiro caso é o mais importante: mensagem que o robô NÃO reconhece também é repetida, nunca tratada como \"desiste, é permanente\". Isso não é descuido: em 30/08 uma proteção parecida desistiu de uma entrega que teria subido, porque tratou uma coisa que não entendia como se fosse veredito. Errar repetindo custa um minuto; errar desistindo perde a entrega e deixa o site na versão velha sem ninguém perceber.\n\nO QUE CONTINUA SEM REPETIÇÃO, DE PROPÓSITO: a CONSTRUÇÃO da imagem. Se ela falhar, é defeito no código, e repetir código quebrado é exatamente esconder o vermelho. Só o transporte da imagem já pronta ganhou repetição.\n\nE SE AS TRÊS FALHAREM, a entrega fica vermelha do mesmo jeito. Ela não engole o erro: quando as três acabam, a imagem nova não está no depósito e o site continua servindo a anterior, e é isso que a tela vai dizer.\n\nUMA COISA QUE VOCÊ PODE QUERER SABER: o log de hoje tinha uma armadilha. Logo acima do erro de verdade havia um aviso vermelho e assustador sobre uma senha de configuração, que é INOFENSIVO e esperado. Quem lê o log de baixo para cima conserta a coisa errada e o problema volta. Isso ficou escrito na armadilha 295, para o próximo robô não cair.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/901",
  verificado_em: "2026-09-03",
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
