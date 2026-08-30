(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-096-o-aviso-do-espelho-velho-entrou-e-achou-um-problema-maior",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "O aviso do inicio de sessao agora mede a idade da pasta, e achou um problema maior embaixo dele",
  detalhe: "Toda sessao de robo comeca com um aviso dizendo em que pasta ela nasceu. Agora esse aviso tambem MEDE quanto essa pasta esta atrasada, e diz uma de quatro coisas, nunca uma quinta: se esta em dia, ele cala a boca; se esta atrasada E o manual de instrucoes divergiu, ele avisa que parte das ordens pode estar REVOGADA; se esta atrasada mas o manual continua igual, ele diz que as ordens valem e so o resto da pasta esta velho; e se nao conseguiu medir, ele diz que nao mediu. Nao medir nunca vira 'esta tudo bem'.\n\nO robo provou a parte mais importante por sabotagem: fez o programa achar que a pasta estava em dia quando nao estava, e o teste ficou vermelho. Sem essa prova, o silencio quando esta tudo bem seria indistinguivel de um aviso quebrado.\n\nMedido na sua pasta, agora: 378 entregas atras, com o manual divergindo. Eram 358 de manha; ela envelhece enquanto os robos trabalham.\n\nO ACHADO MAIOR. Ao terminar, o robo percebeu que o problema e mais fundo do que o que ele consertou. Nao e so o manual que chega velho: e a maquinaria de vigilancia inteira. Os alarmes que avisam um robo quando ele vai repetir um erro conhecido sao reconstruidos a cada sessao a partir dos arquivos DESTA pasta. Com ela atrasada, o alarme local enxerga 7 sinais em vez de 45, e ainda usa a versao errada de um que foi consertado hoje de manha.\n\nA consequencia, dita sem rodeio: consertos que ja entraram na linha principal NAO estao valendo em nenhuma sessao desta casa. Dois robos mediram isso hoje, separadamente, sem saber um do outro.\n\nVirou tarefa, e o pedido nao escolhe a solucao: manda comparar tres caminhos possiveis e escrever o custo e o risco de cada um antes de decidir. Um deles nao e trabalho de robo, e o pedido diz isso com todas as letras: se for o unico caminho seguro, o robo abre um pedido para voce em vez de contornar em silencio.",
  autoridade: "github",
  evidencia: "O aviso veio no PR https://github.com/abundanciabr/sitesdoreino/pull/658 (TAR-045), MERGEADO. Prova nos quatro desfechos, sem rede: em dia => nenhum paragrafo de idade; 358 atras com o manual mexido => fala 'REVOGADA'; 12 atras com o manual igual => fala que as ordens valem, sem a palavra revogada; git mudo => 'NAO MEDIDA', citando INV-CI01. A guarda anti-barulho provada com dente: falsificando a contagem de zero para menos um, o aviso passou a gritar e o teste ficou vermelho (1 failed, 42 passed). Suites: 43 na muralha, 1345 em ci/tests. Prova de fora no espelho real: 378 commits atras. Este PR https://github.com/abundanciabr/sitesdoreino/pull/661 cria a TAR-050, o problema maior, medido por dois robos independentemente (TAR-043 e TAR-045).",
  verificado_em: "2026-08-30",
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
