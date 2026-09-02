(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-028-a-revisao-do-motor-achou-tres-defeitos-e-consertou-os-tres",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "Voce pediu para conferir o motor das mensagens que entrou hoje: tres defeitos achados e consertados",
  detalhe: "As tres partes do motor das mensagens automaticas entraram hoje, uma atras da outra. Voce pediu para revisar antes que qualquer erro virasse habito. Foi o pedido certo: havia tres, e nenhum deles dava erro na tela.\n\nO PRIMEIRO. Um aviso configurado para sair pelo sininho E por e-mail so chegava por um. O sininho saia, e o e-mail do mesmo aviso era barrado pela regra que limita as mensagens do dia, gastando a cota com a mensagem que era ele proprio. Pior: a tela explicava 'ja recebeu 1 hoje', que se le como a regra funcionando direito. Hoje nada esta quebrado, porque tudo sai so pelo sininho. Ia quebrar no dia em que o e-mail entrar, que e justamente o proximo passo da escada.\n\nO SEGUNDO. Quem silencia um tipo de aviso ficava preso na sequencia para sempre. A regra diz, de proposito, que silenciado nao se remarca. So que ninguem mandava a sequencia seguir em frente, entao ela parava ali e era reexaminada de cinco em cinco minutos, sem fim. Onze dias de teste depois, a pessoa continuava travada no primeiro passo.\n\nO TERCEIRO, e o mais serio. Essas pessoas presas ficam na frente da fila, porque a fila atende quem esta esperando ha mais tempo. Encenei uma fila de tres vagas com tres pessoas presas: em quatorze passadas, o aluno novo foi atendido zero vezes. Nenhuma. E nada acusava. Em producao a fila tem duzentas vagas, entao no dia em que duzentas pessoas silenciassem alguma coisa, o motor pararia de atender gente nova em silencio.\n\nOs tres estao consertados no PR 866, cada um com um teste que prova o defeito antes e a cura depois. Escrevi tambem dois testes a mais que existem so para impedir que o meu proprio conserto afrouxe a regra: um garante que voce continua recebendo no maximo uma mensagem por dia, outro garante que uma queda de minutos nao faz a plataforma pular avisos.\n\nO que estava certo tambem foi conferido, e e a maior parte: a trava que protege o fluxo de dinheiro nao foi tocada por nenhum dos tres PRs, a promessa de que a frase nao muda embaixo de quem ja entrou na sequencia tem mecanismo de verdade no banco, e a trava que deixa a pessoa entrar de novo numa sequencia esta correta.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/866",
  verificado_em: "2026-09-02",
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
