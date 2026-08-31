(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-127-o-login-por-senha-esta-completo-e-no-ar",
  tipo: "resposta",
  quando: "2026-08-31",
  titulo: "O projeto de login por senha está COMPLETO e no ar (o PR #798 mergeou e o deploy foi verde)",
  detalhe: "O PR #798 (o botão de resetar senha, no seu painel) pousou e o deploy rodou verde logo em seguida (run 33448959871, 'success', conferido pela API do GitHub, não por um pipe). Com isso, as 3 partes de código do projeto estão TODAS no ar: PR #787 (a célula que guarda a senha, registro 20260831-123), PR #791 (as telas de cadastro e de entrar, registro 20260831-125) e agora este.\n\nO QUE JÁ FUNCIONA NO SITE: quem não tem Google escolhe uma senha em meshcraft.top/cadastro, entra com ela em meshcraft.top/login, e você consegue resetar a senha de qualquer pessoa pelo botão novo no prontuário dela (dentro de /admin/escola/alunos/).\n\nSÓ FALTA UM PASSO, e é seu: colar duas linhas num arquivo de configuração na VPS (TOKENS_SENHA_FUNIL e TOKENS_SENHA_ADMIN, os mesmos valores que já existem para TOKENS_ACEITOS_FUNIL e TOKENS_ACEITOS_ADMIN — nenhuma senha nova para gerar, nenhum custo novo). Vou te mandar o bloco pronto para colar.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33448959871",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: "20260831-124-a-ultima-parte-do-login-por-senha-esta-pronta",
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
