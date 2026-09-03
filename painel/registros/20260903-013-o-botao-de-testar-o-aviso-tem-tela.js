(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-013-o-botao-de-testar-o-aviso-tem-tela",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O botão de testar o aviso ganhou tela no seu painel",
  detalhe: "Terceiro dos quatro passos combinados com você. As duas peças de bastidor já estavam prontas; agora existe o botão de verdade, no lugar onde você já entra.\n\nONDE ESTÁ: /admin/, na Visão geral, o oitavo cartão da grade, chamado \"Testar o aviso no celular\". Ele abre uma tela pequena com um botão só.\n\nO QUE ACONTECE QUANDO VOCÊ CLICA: um aviso de teste é mandado para o aparelho onde você ligou os avisos, e a tela volta dizendo para quantos aparelhos ele chegou. Se disser \"chegou em 1 aparelho\", o canal inteiro está funcionando, do clique até a tela do seu celular. Se disser \"zero aparelhos\", quer dizer que você ainda não clicou em \"Ligar os avisos\" em nenhum aparelho, e a própria tela explica isso, sem parecer defeito.\n\nO QUE ESTÁ GARANTIDO POR DESENHO: o botão só pode mandar aviso para o SEU PRÓPRIO aparelho. Não existe campo para escolher outra pessoa, então não há como esse botão, por engano, tocar o celular de um aluno.\n\nO QUE FALTA: o quarto e último passo, que é a tela do próprio site (não do seu painel) aprender a mostrar o texto certo quando ESSE tipo de aviso chega no celular de alguém. Sem ele o teste ainda funciona (ele usa o texto genérico), mas o texto fica menos claro do que os outros avisos que a escola já manda.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/910. 12 testes novos, 749 verdes na célula admin, black limpo. Duas mutações e dois vermelhos certeiros: aceitar um destinatário vindo do formulário mata a cerca de quem recebe; esconder a frase de zero aparelhos mata o teste do desfecho mais importante. As 13 muralhas do repositório em PASS, medidas contra o commit real (não contra o índice, que mentiria zero mudanças).",
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
