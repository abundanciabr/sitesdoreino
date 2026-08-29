(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-092-o-deploy-que-a-vps-recusa-agora-se-conserta-sozinho",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "O maior desperdício de robô que eu consegui medir agora se conserta sozinho",
  detalhe: "Existe um tropeço que se repetia mais que qualquer outro: o servidor recusa a conexão na hora de publicar uma entrega, e o deploy fica vermelho. Ele apareceu SEIS vezes em três dias — e apareceu de novo hoje, bem no meio do trabalho de curá-lo.\n\nO que ele custava: nada quebrava de verdade (o site continuava no ar servindo a versão anterior), mas cada vez um robô parava, relia a lição, testava a porta do servidor na mão, decidia se era instabilidade passageira ou problema de configuração, mandava repetir e ia conferir. Um diagnóstico do zero, no modelo mais caro, para um procedimento em que TODAS as decisões já estavam escritas.\n\nEsse era o ponto: a lição existia, estava certa e completa — e mesmo assim era refeita à mão toda vez. Documentar não resolveu; virar máquina resolveu.\n\nAGORA É UM COMANDO SÓ. Ele confere o resultado real da publicação, verifica se a falha é mesmo aquela (e não outra coisa disfarçada), testa a porta do servidor, distingue instabilidade passageira de problema de configuração, repete com uma pausa entre as tentativas — e PARA na terceira, escrevendo para você o que aconteceu, em vez de insistir.\n\nDUAS RECUSAS QUE SÃO O PONTO: se a falha não for essa, ele NÃO repete (repetir esconderia um defeito real atrás de três tentativas); e se ele não conseguir medir a porta, ele para em vez de tentar na esperança. 'Não consegui medir' nunca vira 'pode ir'.\n\nPROVA CONTRA A REALIDADE: rodei contra as três publicações que falharam de verdade hoje. Nas duas que eram esse tropeço, ele mandou repetir; na terceira, que era outra coisa, ele recusou repetir e mandou olhar o log. Ele acertou os três sozinho.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/500",
  verificado_em: "2026-08-29",
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
