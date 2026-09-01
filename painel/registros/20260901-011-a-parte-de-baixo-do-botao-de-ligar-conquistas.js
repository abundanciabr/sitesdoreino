(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-011-a-parte-de-baixo-do-botao-de-ligar-conquistas",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A parte de baixo do botao de ligar medalhas e marcos esta pronta",
  detalhe: "Depois da conversa de contrato, esta e a metade que ninguem ve: a parte das conquistas passou a saber responder 'estas sao as medalhas e os marcos desta escola, ligados e desligados' e 'ligue esta aqui'. A SUA TELA ainda nao mostra isso — ela e o proximo passo, e vem em seguida.\n\nO QUE ELA JA AVISA, antes de voce clicar em qualquer coisa: quando ligar nao vai adiantar. Sao tres avisos possiveis, e eles existem porque um zero sem explicacao parece defeito da tela:\n\n1. 'a conta automatica ainda nao existe' — as medalhas que a escola concederia sozinha dependem de um motor que e a proxima tarefa. Ligar uma hoje nao concede nada a ninguem.\n2. 'nada no site produz esse numero ainda' — a medalha 'Dez forjas' conta pecas seladas no medidor de esforco, que nao existe; a 'Mao amiga' conta respostas aceitas no forum, que ainda nao avisa a gamificacao.\n3. 'so sai pela mao da equipe' — a medalha de Fundador nao tem conta nenhuma: alguem concede.\n\nOS MARCOS NAO TEM AVISO NENHUM, e isso e a boa noticia: ligar um marco ja funciona hoje de ponta a ponta. Ele aparece na trilha do aluno, o aluno manda a prova, e voce aceita na fila.\n\nUMA COISA QUE EU CONSERTEI NO CAMINHO, e vale contar porque e o tipo de erro que se esconde: um dos testes novos PASSOU mesmo com a regra quebrada de proposito. Eu tinha escolhido nomes que davam a mesma ordem dos dois jeitos, entao ele nao provava nada. Reescrevi com nomes escolhidos contra a ordem alfabetica, e so ai ele ficou vermelho quando devia. Teste que nao fica vermelho quando a regra some nao esta provando a regra.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/817, implementando o contrato emendado no PR #816 (provedor primeiro, RITOS §3). Suite da celula 211 passed (eram 202; 9 testes novos). ci/freeze-de-contrato.sh gamificacao PASS, identico ao congelado, com 6 operacoes de autenticacao conferida na fonte. PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195): removida a chave de classe da ordenacao, 'assert [aaa-medalha, zzz-marco] == [zzz-marco, aaa-medalha]'; removido o aviso do motor, 'assert [] == [sem-motor-de-criterio]'. O guarda do 401 deixou de ser lista digitada e passou a LER o contrato congelado, cobrindo toda operacao de leitura que a plataforma promete.",
  verificado_em: "2026-09-01",
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
