(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-009-a-frase-honesta-do-aviso-ja-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "A frase honesta do aviso já está no ar",
  detalhe: "O conserto que você aprovou entrou na plataforma e eu conferi que chegou de verdade.\n\nO QUE MUDOU PARA QUEM USA O SITE: quando o navegador da pessoa é que recusa os avisos, a tela para de dizer 'tente de novo mais tarde' e passa a dizer o que fazer, mandando olhar os ajustes de privacidade do navegador. Quando quem falha é o nosso servidor, a frase continua sendo 'tente mais tarde', porque ali isso é verdade. Nos três idiomas.\n\nCOMO EU SEI QUE CHEGOU, e não é só o pipeline dizendo que sim: eu baixei o arquivo do site publicado e conferi dentro dele que os dois caminhos de falha estão separados, e que ninguém os juntou de volta. Essa é a prova que vale, porque ela olha o que o aluno recebe, não o que a nossa máquina achou que mandou.\n\nO QUE AINDA ESPERA POR VOCÊ: ligar as mensagens push no seu Brave. Isso é do seu computador e nenhum deploy conserta. O caminho está no registro anterior.",
  autoridade: "github",
  evidencia: "Merge do PR https://github.com/abundanciabr/sitesdoreino/pull/905 no commit ddeee02c. Deploy: run 33705577865 do deploy-celula, conferido por gh run view --json (status=completed, conclusion=success), nunca por exit de pipe. Prova de fora: https://meshcraft.top/static/funil/avisos.js baixado depois do deploy (HTTP 200, 9697 bytes) contém o tratador próprio da recusa do navegador na linha 172, sem .catch genérico dentro do inscrever e sem o desfecho do navegador vazando para o caminho do servidor.",
  verificado_em: "2026-09-03",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
