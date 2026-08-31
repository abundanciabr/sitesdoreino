(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-036-para-a-tela-do-menu-funcionar-falta-um-passo-seu-na-vps",
  tipo: "pendencia",
  quando: "2026-08-31",
  titulo: "Para a tela do menu do topo funcionar, falta uma linha sua no servidor",
  detalhe: "A tela /admin/menu/ ja esta no ar, mas ela precisa conversar com o lugar onde o menu fica guardado (o registro de sites), e essa conversa exige uma senha de maquina. Senha de maquina nunca viaja pelo Git nem passa por robo (e a Lei 5 da casa), entao ela so pode nascer dentro do servidor.\n\nO QUE VOCE FAZ: entre no servidor e cole ESTA UNICA LINHA. Ela nao pergunta nada, nao pede nada, gera a senha la dentro, liga os dois lados e reinicia o que precisa. Se algo estiver estranho, ela para sozinha dizendo PAROU POR SEGURANCA e nao mexe em nada.\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-do-menu.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nA linha e para colar DENTRO DO SERVIDOR: a janela em que o comeco da linha ja diz deploy@srv ou root@srv. Nao e para colar no seu computador.\n\nQuando terminar, ela escreve PRONTO e o endereco para abrir. Rodar de novo e seguro: se ja estiver ligado, ela reusa o que existe em vez de trocar.\n\nENQUANTO ISSO NAO ACONTECE: nada quebra. O menu que ja esta no site continua exatamente como esta, e a tela /admin/menu/ abre dizendo, em portugues, que ainda nao consegue falar com o registro de sites. E so a EDICAO pela tela que espera por este passo.",
  autoridade: "sessao",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: "O menu do site continua funcionando como esta, mas voce nao consegue muda-lo pela tela: cada mudanca voltaria a depender de um robo e de um PR.",
  recomendacao: "Rodar a linha. Ela leva menos de um minuto, e libera voce para mexer no menu quando quiser, sozinho.",
  reversivel: true,
  impacto: "medio"
});})();
