(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-053-o-menu-do-topo-esta-no-ar-nos-tres-idiomas",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O menu do topo esta no ar, nos tres idiomas, e a tela de entrar ficou sem menu de proposito",
  detalhe: "Abra https://meshcraft.top e voce ve, no alto da pagina: Inicio, Forum, Cadastro. Em espanhol (https://meshcraft.top/es/) o mesmo menu aparece como Inicio, Foro, Registro. Em ingles (https://meshcraft.top/en/), Home, Forum, Sign up.\n\nAgora entre em https://meshcraft.top/login. Nao tem menu nenhum ali, e isso e de proposito: quem esta entrando tem uma tarefa so, e um menu ali e convite para abandona-la. Era exatamente o que voce pediu: em algumas paginas nao ter menu.\n\nMEDIDO NA INTERNET PUBLICA, depois do deploy, e nao na maquina do robo:\n  /            200, mostrando Inicio Forum Cadastro\n  /es/         200, mostrando Inicio Foro Registro\n  /en/         200, mostrando Home Forum Sign up\n  /cadastro    200, com menu\n  /login       200, SEM menu\n  /pt-br/      404 (o idioma padrao mora na raiz nua, como ja era a lei da casa)\n\nUm detalhe que so aparece olhando o endereco dos links: em espanhol, o link do cadastro vira /es/cadastro (traduzido), mas o do forum continua /forum/ (nao traduzido). Isso e correto: o forum e outra parte do sistema e nao tem versao em espanhol; se o link fosse traduzido, ele levaria a uma pagina que nao existe.\n\nOS PRs, todos mergeados: 704 (o contrato), 714 (o motor que guarda o menu), 710 (o menu desenhado no site), 713 (a tela de configuracao), 718 (a correcao de um endereco que nao podia virar link), 725 e 726 (as licoes das celulas). Deploys conferidos por gh run view --json: catalogo run 33418134374 success, funil run 33418368555 success.\n\nO QUE AINDA FALTA, e esta escrito em registro proprio: a tela /admin/menu/ ja esta no ar, mas so vai deixar voce EDITAR depois de um passo seu no servidor (uma linha de colar). Ate la o menu que voce ve e o que veio de fabrica.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/726",
  verificado_em: "2026-08-31",
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
