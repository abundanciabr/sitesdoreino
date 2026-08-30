(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-094-a-porta-da-gamificacao-abriu-e-o-proximo-degrau-esta-escrito",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A gamificacao ganhou a porta por onde conversa com o resto do site, e a celula destravou",
  detalhe: "A parte nova do site ja tinha o combinado escrito e congelado, mas ainda nao tinha a porta por onde cumprir esse combinado. Isso deixava todo trabalho seguinte na celula travado: o conferidor comparava o documento com o que a parte responde, nao encontrava resposta nenhuma, e reprovava.\n\nAgora a porta existe, com as duas conversas que o combinado previa: uma que devolve a etiqueta de varios alunos de uma vez (para o forum decorar muitos nomes com um pedido so) e outra que devolve a situacao do proprio aluno. A primeira nunca entrega e-mail nem ponto cru, so nivel e titulo; aluno desconhecido simplesmente nao aparece na resposta.\n\nA prova e a que importava: o conferidor saiu de RECUSADO para APROVADO, com o combinado intocado. Quem mudou foi a implementacao, que e a ordem certa: a promessa manda, o cumprimento obedece. O robo ainda quebrou a porta de proposito tres vezes para mostrar os alarmes tocando, inclusive um que pega ponto vazando para fora.\n\nO PROXIMO DEGRAU JA ESTA ESCRITO, com um cuidado que so apareceu porque alguem mediu. Quando a parte nova for publicada no servidor, uma configuracao chamada SITE_ID precisa ir junto. Se ela faltar, a etiqueta de TODOS os alunos some e NENHUMA tela quebra: e a falha que melhor se esconde. Por isso a tarefa do provisionamento ja nasce exigindo que o programa se RECUSE a terminar sem esse campo, em vez de so mencionar.\n\nEssa mesma tarefa vai te entregar o unico passo manual que a gamificacao inteira pede de voce: um bloco unico para colar, com a janela indicada e com mensagem de 'parou por seguranca' se algo estiver estranho.",
  autoridade: "github",
  evidencia: "A porta veio no PR https://github.com/abundanciabr/sitesdoreino/pull/656 (TAR-044), 15 arquivos. PROVA CRUA do destravamento, mesmo comando e mesmo ambiente: ANTES 'contrato/gamificacao ERROR exportar contrato vivo de gamificacao: exit code 1 / Unknown command: export_openapi / EXIT=2'; DEPOIS 'contrato/gamificacao PASS identico ao congelado (263 linhas comparadas)' e 'seguranca/gamificacao PASS 2 operacao(oes) com autenticacao conferida na fonte / EXIT=0'. Mais 96 testes verdes na celula, 13 muralhas PASS e tres sabotagens provadas por assercao (armadilhas/195), incluindo XP vazando na etiqueta publica. Este PR https://github.com/abundanciabr/sitesdoreino/pull/660 cria a TAR-049, o degrau seguinte, com a exigencia do SITE_ID escrita dentro.",
  verificado_em: "2026-08-30",
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
