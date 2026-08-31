(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-041-falta-voce-ligar-a-chave-do-aviso-no-celular",
  tipo: "pendencia",
  quando: "2026-08-31",
  titulo: "Falta um passo seu: ligar a chave do aviso no celular",
  detalhe: "O aviso na tela do celular esta construido de ponta a ponta: o site pede a permissao, guarda o aparelho e sabe enviar. Falta UMA coisa, e ela so pode ser feita por voce, dentro do servidor: a chave de seguranca que a Google, a Apple e a Mozilla exigem para aceitar um aviso vindo do nosso site. Segredo nao viaja por robo nem por Git (e a Lei 5 da casa), entao este passo e seu.\n\nO QUE VOCE FAZ: entra na VPS e cola UMA linha. O script gera a chave la dentro, guarda as duas metades nos lugares certos e reinicia so o que precisa. A metade secreta nao aparece na tela em momento nenhum, nem no que voce me mandar depois.\n\nA LINHA (cole dentro da VPS, num prompt que comeca com deploy@srv ou root@srv):\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-aviso-no-celular.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nO QUE ACONTECE ENQUANTO VOCE NAO FAZ: nada quebra, e ninguem ve botao quebrado. O cartaz de ligar os avisos simplesmente nao aparece para ninguem, de proposito, e os avisos continuam chegando no sininho do site como sempre. Botao que nao funciona e pior que botao nenhum.\n\nRODAR DE NOVO E SEGURO: se a chave ja existir, ele reaproveita. Isso importa mais aqui do que nos outros scripts: uma chave nova desligaria, de uma vez e em silencio, todo aparelho que ja estivesse recebendo aviso.",
  autoridade: "rito",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/725 (TAR-082, degrau D). O script tem 6 testes que o EXECUTAM contra uma plataforma de mentira, e um deles prova que a metade secreta nunca aparece na saida.",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: 7,
  se_eu_nao_decidir: "O aviso no celular fica construido e desligado. Ninguem ve botao quebrado, mas ninguem recebe aviso no celular tambem, e o trabalho dos quatro degraus fica parado no ultimo centimetro.",
  recomendacao: "Rodar a linha hoje ou amanha. Sao 30 segundos dentro da VPS, o script se recusa a agir se algo estiver estranho, e nenhum segredo passa por mim nem aparece na tela.",
  reversivel: true,
  impacto: "medio"
});})();
