(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-118-a-regra-da-sugestao-pronta-pagava-demais",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A regra que voce escolheu pagava demais, e isso foi achado antes de voce liga-la",
  detalhe: "Voce escolheu ligar primeiro a regra 'ter a propria sugestao feita', 40 pontos. Fui conferir a regra antes de voce clicar, e ela tinha um defeito.\n\nO QUE ESTAVA ERRADO: o aviso que a Caixa manda nao diz 'a sugestao ficou pronta'. Ele diz 'a equipe mudou o status', e o status pode virar seis coisas diferentes. A regra escutava o aviso inteiro, sem olhar PARA QUAL status foi. Resultado: mover uma sugestao pelo caminho normal (em analise, planejada, em desenvolvimento, pronta) pagava 40 pontos em CADA passo. Quatro passos, 160 pontos, por uma sugestao so. E essa regra nao tem teto diario nem espera, entao nada segurava.\n\nQUEM CONSEGUIA DISPARAR ISSO: so a equipe, porque so a equipe muda status. Nenhum aluno chegava perto. Ou seja, o numero que ia inflar era o SEU. Mesmo assim vale consertar: um numero que a pessoa nao consegue explicar e exatamente o que a lei da gamificacao manda evitar.\n\nO CONSERTO, e o cuidado que ele exigiu: a regra ganhou um campo que diz 'so pague quando o status novo for PRONTA'. Parece obvio, mas tem uma armadilha aqui: a lei diz que no dia em que esta parte do sistema virar um 'motor de regras generico' — uma linguagenzinha de condicoes onde da para escrever qualquer coisa — e para PARAR e conversar com voce. Entao eu nao fiz um campo de condicao livre. Fiz um campo com nome concreto, que compara uma coisa so, e deixei um teste que reprova quem tentar generalizar isso depois.\n\nE UM DETALHE QUE QUASE PASSOU: consertar o arquivo que CRIA as regras nao conserta a regra que ja esta gravada no banco. Sao coisas diferentes, e essa confusao ja custou caro aqui antes (um travessao sobreviveu no forum depois de uma limpeza que se declarou completa). Entao junto do conserto vai uma correcao da linha que ja existe.\n\nUMA COISA BONITA: o nome que aparece na sua tela ja estava certo. Ele diz 'Ter a propria sugestao feita' — que e exatamente o comportamento certo. Era o codigo que nao alcancava o proprio rotulo.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/792. PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), sem rede: removida a conferencia do status, os quatro status que NAO deviam pagar passam a pagar, com 'Left contains one more item: <LancamentoDeXP: +40 sugestao-implementada 2026-08-31>' um para cada. Com o conserto, 159 passed na celula (eram 150; 9 testes novos). O teste que da o numero e test_o_funil_inteiro_paga_UMA_vez_so: tres mudancas de status e o perfil fecha em 40, com UM lancamento — antes, 120. O alcance foi medido lendo services/sugestoes/apps/core/moderacao.py, que se declara 'o lado da equipe'. ci/contract_freeze.py gamificacao PASS (identico ao congelado, 406 linhas): o qualificador e interno e nao mexe no contrato. black limpo.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
