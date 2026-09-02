(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-047-a-ia-do-forum-foi-recusada-e-o-motivo-nao-era-o-que-a-tela-dizia",
  tipo: "incidente",
  quando: "2026-09-02",
  titulo: "Voce apertou o botao da IA e levou a mensagem errada; os dois defeitos estao consertados",
  detalhe: "Voce ligou a IA, apertou 'Gerar resposta' e recebeu 'pode ser a internet do servidor'. Nao era a internet, e eu tinha te dado uma frase que apontava para o lugar errado. Dois defeitos, os dois meus, os dois consertados.\n\nO QUE REALMENTE ACONTECEU: existem dois tipos de chave da Anthropic. A antiga ja vem amarrada a um espaco de trabalho; a nova, que e a que voce criou, e ligada a VOCE, e por isso ela nao sabe sozinha em qual espaco de trabalho agir. A Anthropic recusou pedindo essa informacao. A rede estava perfeita, a chave estava certa, e o dinheiro nao foi tocado.\n\nO CONSERTO 1: o forum agora sabe mandar essa informacao. Voce vai rodar o MESMO comando de antes, e ele passa a fazer uma segunda pergunta, o id do espaco de trabalho. Essa segunda pergunta aparece na tela enquanto voce digita (diferente da chave, que fica invisivel), porque ela nao e segredo e ver o que colou evita erro. Se voce nao souber o que responder, e so apertar Enter.\n\nO CONSERTO 2, e este e o que mais me incomodou: a tela juntava duas coisas opostas na mesma frase. 'A chamada nem saiu daqui' e 'eles responderam recusando' pedem consertos contrarios, e eu tinha escrito uma frase que servia para os dois. Agora cada situacao tem a frase dela, incluindo as duas que enganam ate quem entende: falta de espaco de trabalho e conta sem credito chegam com o mesmo numero de erro de coisas completamente diferentes. E quando eu nao souber o motivo, a tela diz o numero e admite que nao sabe, em vez de chutar.\n\nO QUE EU APRENDI E GUARDEI: eu supus, antes de medir, que era falta de credito. Estava errado, e so o log disse a verdade. Ficou escrito na memoria do projeto, com a medicao junto.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/883. Log de producao: HTTP 400 'anthropic-workspace-id is required when authenticating with an identity-linked API key'. Medicao com transporte dublado: o SDK NAO manda o cabecalho quando a chave e passada no codigo, mesmo com a variavel de ambiente posta (tabela nos tres casos, na armadilhas/291). Suite do forum 273 verde (eram 265), ci/tests do script 17 verde (eram 12). Quatro sabotagens, quatro vermelhos. Toca infra/ e ci/, em CODEOWNERS.",
  verificado_em: "2026-09-02",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: "A IA continua desligada na pratica: o botao aparece e recusa. Nada quebra e nada e cobrado, mas o ajudante nao ajuda.",
  recomendacao: "Rodar de novo o mesmo comando de antes, na VPS, depois que este conserto subir. Ele vai pedir a chave (invisivel, como da outra vez) e o espaco de trabalho (visivel). Se voce nao achar o id, aperte Enter e me avise: eu te mostro onde ele fica.",
  reversivel: true,
  impacto: "medio"
});})();
