(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-014-o-instrumento-de-testar-o-aviso-esta-completo",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O instrumento de testar o aviso na tela do celular está completo",
  detalhe: "Fecha, de ponta a ponta, o pedido que você fez hoje de manhã. Recapitulando o caminho inteiro, num lugar só:\n\nTUDO COMEÇOU com você clicando em 'Ligar os avisos' e vendo 'Não deu certo agora'. A causa era o seu Brave, que vem de fábrica com essa opção desligada. Consertei a mensagem do site para os próximos casos (isso já estava no ar antes deste plano) e você pediu, além disso, um jeito de confirmar que o canal inteiro funciona sem precisar de mim toda vez.\n\nO QUE EXISTE AGORA, e já está tudo no ar: em /admin/, na Visão geral, o botão 'Testar o aviso no celular'. Você clica, e a tela diz para quantos aparelhos o aviso saiu. Se saiu para pelo menos um, o canal está de ponta a ponta funcionando: do seu clique até a tela do seu celular. Se disser zero, é porque ainda falta você ligar os avisos em algum aparelho, e a tela já explica isso.\n\nO QUE VOCÊ VAI VER NO CELULAR quando testar: um aviso do Meshcraft dizendo 'Deu certo. Este é o teste que você pediu.' Frase fixa, nos três idiomas, só para esse botão.\n\nQUATRO PEÇAS, quatro PRs, cada uma provada sozinha antes de eu seguir para a próxima: o contrato que autoriza a porta, a peça que guarda o aparelho e manda o aviso, o botão no seu painel, e o texto que aparece no celular.",
  autoridade: "github",
  evidencia: "PRs https://github.com/abundanciabr/sitesdoreino/pull/907, https://github.com/abundanciabr/sitesdoreino/pull/908, https://github.com/abundanciabr/sitesdoreino/pull/909, https://github.com/abundanciabr/sitesdoreino/pull/910, https://github.com/abundanciabr/sitesdoreino/pull/911 (este). 566 testes verdes na célula funil (48 deles sobre avisos), black limpo, cerca anti-genérico confirmando que o assunto de teste não caiu no texto vago. 13 muralhas do repositório em PASS, medidas contra o commit real.",
  verificado_em: "2026-09-03",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: "O instrumento fica pronto e esperando. Você continua sem saber, sem clicar no botão, se os seus próprios avisos estão chegando.",
  recomendacao: "Depois que o PR #911 estiver no ar (eu aviso), abra /admin/, clique em 'Testar o aviso no celular' e me conta o que apareceu.",
  reversivel: true,
  impacto: "baixo"
});})();
