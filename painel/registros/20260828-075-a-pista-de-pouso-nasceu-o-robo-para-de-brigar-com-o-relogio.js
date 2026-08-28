(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-075-a-pista-de-pouso-nasceu-o-robo-para-de-brigar-com-o-relogio",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "A pista de pouso nasceu — o robô para de brigar com o relógio para conseguir entregar",
  detalhe: "Com a chave que você criou, a primeira parte da Onda 4 está no ar.\n\nO problema que ela resolve é o que você viu hoje: uma entrega minha de 4 arquivos precisou de oito tentativas. Não por desleixo — é que a versão oficial do projeto anda cerca de 98 vezes por dia, cada tentativa gasta 90 segundos de teste, e nesse intervalo ela anda de novo. O robô perde a corrida contra o relógio, e ser mais rápido não adianta.\n\nAgora ele não corre mais: ele pendura uma etiqueta pedindo pouso e vai embora. A pista atende uma entrega por vez, atualiza, confere e aprova. Se a versão oficial andar no meio, o problema passa a ser da pista — que tem paciência e não gasta a sua franquia.\n\nÉ opcional de propósito. Quem não pendurar a etiqueta continua fazendo exatamente como antes. Se a pista tiver algum defeito, ninguém é atingido — e por isso ela pode ser experimentada sem risco. As partes seguintes (publicar na ordem certa, desfazer sozinha se quebrar, e tirar de vez o merge da mão do robô) só entram depois que esta provar que funciona no mundo real.\n\nTrês cuidados que valem contar, porque cada um é uma armadilha que teria custado caro:\n\nPrimeiro, ela usa a SUA chave e não a chave automática do GitHub. Se usasse a automática, a aprovação não contaria como acontecimento novo e a publicação no servidor nunca dispararia — a plataforma congelaria em silêncio.\n\nSegundo, quem julga é sempre a versão oficial das regras, nunca a versão que está dentro da entrega sendo julgada. Sem isso, uma entrega que mudasse as regras mudaria o próprio juiz.\n\nTerceiro, ela chama a próxima entrega ao terminar. Isso parece detalhe e não é: o mecanismo do GitHub que garante 'um por vez' NÃO é uma fila — quando chega um terceiro pedido, ele cancela o que estava esperando. Sem essa chamada no fim, um pedido de pouso se perderia em silêncio. Uma das cinco IAs afirmou que dava para usar como fila; outra provou pela documentação que não. A segunda estava certa.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/431",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260828-072-a-pista-de-pouso-precisa-de-uma-chave-sua",
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
