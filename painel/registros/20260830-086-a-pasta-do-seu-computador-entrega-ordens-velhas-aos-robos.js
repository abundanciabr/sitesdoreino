(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-086-a-pasta-do-seu-computador-entrega-ordens-velhas-aos-robos",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "A pasta do projeto no seu computador esta 358 entregas atrasada, e e ela quem entrega o manual de instrucoes aos robos",
  detalhe: "Descobri hoje um defeito que nao aparece no site, mas que atrapalha todo robo que trabalha aqui.\n\nO projeto tem um manual de instrucoes na raiz. Todo robo recebe esse manual automaticamente, antes de ler qualquer outra coisa, e ele vem da PASTA DO SEU COMPUTADOR, nao da versao publicada. Essa pasta esta 358 entregas atrasada.\n\nO efeito, medido hoje: o manual da sua pasta manda escolher a mao o numero de um aprendizado novo. A versao publicada manda PEDIR esse numero a um sorteio central, justamente porque escolher a mao faz dois robos escolherem o mesmo. Um robo do lote de hoje seguiu a instrucao que RECEBEU, escolheu a mao, bateu de frente com outro robo e foi reprovado. A regra certa tinha sido consertada hoje mesmo, algumas horas antes, por outro robo.\n\nPor que isso e pior do que parece: o robo nao tem como desconfiar. Ele nao leu um arquivo velho por descuido; ele recebeu ordens velhas antes de comecar. Cada lei nova que voce aprova demora a valer de verdade enquanto essa pasta ficar atras, e ninguem avisa.\n\nNAO ATUALIZEI A PASTA. Ela e compartilhada: ha arquivos de outras sessoes ali que nao estao guardados em lugar nenhum, e existe uma trava justamente para eu nao passar por cima do trabalho de outro robo. Passar por cima ja aconteceu neste projeto, e foi caro.\n\nO conserto que deixei encomendado nao e atualizar a pasta: e o aviso que ja aparece no comeco de toda sessao passar a MEDIR o atraso e dizer em voz alta quando ele existir. Assim o robo sabe desconfiar do proprio manual. E o pedido inclui o cuidado de nao falar quando estiver tudo em dia, para o aviso nao virar barulho que todo mundo aprende a ignorar.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/650 (este PR, que cria a TAR-045). MEDIDO na sessao principal em 30/08/2026: `git rev-list --count HEAD..origin/main` = 358; `diff <(git show origin/main:CLAUDE.md) CLAUDE.md` acusa divergencia, e a linha 36 do arquivo local diz 'NNN = proximo numero livre' contra a linha 57 do publicado, que diz 'o NNN se PEDE, nao se escolhe'. O robo afetado foi o da TAR-041, que reportou o fato antes de eu medir; conferi na fonte em vez de repassar o relato. A regra certa veio da armadilhas/227, mergeada hoje. O custo anterior de ler do espelho esta na armadilhas/148.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
