(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-035-o-robo-parou-de-reprovar-quando-a-internet-la-fora-falha",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "O conferente do painel parou de reprovar entrega boa quando a internet lá fora falha",
  detalhe: "Existe um robô que abre o seu painel num navegador de verdade, a cada entrega, e confere se ele está inteiro. Hoje ele reprovou uma entrega que não tinha defeito nenhum. Mandaram ele conferir de novo, sem mudar uma vírgula, e ficou tudo verde. Isso é o pior tipo de alarme: o que toca sem motivo, porque ensina todo mundo a ignorar alarme.\n\nO motivo. O painel pergunta duas coisas ao GitHub enquanto abre (quantas entregas estão na fila, como foram as últimas). Quando essa conversa com o lado de fora falha, o navegador reclama. O painel foi feito para aguentar isso e avisa na tela: \"não consegui perguntar ao GitHub\". Só que o conferente contava aquela reclamação como defeito NOSSO.\n\nMetade disso já tinha sido curada em 29 de agosto. Ficou de fora uma família de reclamação que o navegador anota sem dizer de onde veio, e essa caía sempre do nosso lado.\n\nO conserto, em uma frase: quando a reclamação não diz de onde veio, o conferente passa a ler o que ela diz. Se ela conta que um pedido a um endereço de fora foi barrado, o assunto é da rede alheia e não reprova mais.\n\nO cuidado que fez esta entrega demorar mais do que parece. O endereço meshcraft.top, que é o do seu próprio site, está na lista dos endereços de fora, e o painel tem links para ele na cara. A correção óbvia (\"se o texto citar um endereço da lista, não é nosso\") teria feito qualquer defeito real que por acaso mencionasse o seu site perder o poder de reprovar. Seria trocar um guarda que pisca por um guarda que dorme, e o que dorme é bem pior. Por isso a regra ficou mais estreita: não basta o texto citar o endereço, ele tem que ser o alvo do pedido que falhou.\n\nProva: o teste que o próprio arquivo carrega ganhou quatro casos novos, e cada um foi conferido apagando a regra que ele protege e vendo o teste ficar vermelho com o nome do caso na tela. Três apagões, três vermelhos certeiros, nenhum atingiu caso que não fosse o dele.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/839",
  verificado_em: "2026-09-01",
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
