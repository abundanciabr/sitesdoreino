(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-017-trava-de-merge-nativa-ligada",
  tipo: "resposta",
  quando: "2026-08-26",
  titulo: "A trava de merge do GitHub está LIGADA — nem o dono consegue mais mergear com vermelho",
  detalhe: "Você perguntou qual das duas opções da tela clicar. A resposta é: nenhuma — a trava foi ligada pelo robô, pelo mesmo canal que ele usa para abrir e mergear PR. Você não precisa clicar em nada.\n\nO que passou a valer na main, a partir de hoje: ninguém escreve direto nela (todo trabalho entra por Pull Request); ninguém apaga a main; ninguém reescreve a história dela; e o botão de merge só destrava depois que as DUAS provas do robô ficam verdes (as muralhas e o portão da célula). Antes, o botão verde funcionava com tudo vermelho — quem segurava era só a disciplina do robô.\n\nNão existe exceção para ninguém, nem para você como dono da conta: o GitHub responde 'current_user_can_bypass: never'. A porta de emergência não é um atalho escondido, é desligar a trava — um ato visível, que fica registrado.\n\nA prova não é print de tela: o robô TENTOU escrever na main por fora, como um invasor faria, e o GitHub recusou com a mensagem 'as mudanças precisam passar por um Pull Request; 2 de 2 verificações obrigatórias são esperadas'. Nada foi gravado.\n\nCom isso fecha a pendência mais velha do seu painel — aberta em 19/08, quando essa proteção ainda era paga.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/rules/21570247 — recusa medida: HTTP 409 'Repository rule violations found / Changes must be made through a pull request / 2 of 2 required status checks are expected'",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260819-001-h3-trava-de-merge-nativa",
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
