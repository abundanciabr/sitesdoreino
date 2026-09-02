(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-049-o-rascunho-da-ia-aparece-ao-vivo",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O rascunho da IA passa a aparecer ao vivo, palavra por palavra",
  detalhe: "Voce pediu para ver a resposta sendo escrita em vez de encarar uma tela parada, e o motivo era bom: foi esse silencio de alguns segundos que te fez achar que o botao estava quebrado.\n\nCOMO FICA: voce aperta 'Gerar resposta', o botao vira 'Escrevendo...', e o texto vai nascendo dentro da caixa de resposta enquanto ela escreve. O cursor ja fica la, e a caixa rola sozinha para acompanhar. Nao ha mais momento nenhum em que a tela parece morta.\n\nUMA ESTREIA, E ELA MERECE SER DITA: esta e a primeira vez que uma pagina publica do site tem JavaScript. Ate hoje, nenhuma tinha uma linha.\n\nPOR ISSO ELE FOI FEITO PARA PODER QUEBRAR. O botao continua sendo um formulario comum. O script apenas se mete na frente quando existe e funciona. Se ele nao carregar, se o navegador for antigo, ou se a conexao ao vivo falhar no meio, o botao volta a fazer o que faz hoje: manda, a pagina recarrega, e o texto chega inteiro de uma vez. Nenhuma tela do forum passa a depender de script, e isso virou lei escrita da celula, com teste que reprova quem tentar mudar.\n\nSE DER ERRO NO MEIO, o aviso aparece na propria caixa, em portugues, com a mesma frase de sempre para cada motivo. E se o ao vivo falhar por conta dele mesmo, ele se aposenta sozinho e avisa: aperte de novo, que vem pelo caminho antigo.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/885. Suite do forum 287 verde (eram 277; 10 casos novos). O duble dos testes devolve um corpo text/event-stream real, com a sequencia de eventos da API medida antes de o codigo existir, entao o SDK faz o mesmo parsing que faz em producao. Cinco sabotagens e cinco vermelhos, entre elas a que prova que a tela NAO depende do script. travessao, mapa do site e mapa de celulas PASS.",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
