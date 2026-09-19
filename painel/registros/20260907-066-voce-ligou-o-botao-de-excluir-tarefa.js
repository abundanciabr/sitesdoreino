(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-066-voce-ligou-o-botao-de-excluir-tarefa",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "Voce ligou o botao de excluir tarefa, e a area administrativa esta com a chave",
  detalhe: "O roteiro terminou com PRONTO na VPS: a chave chegou ao lugar certo (93 caracteres, dentro do container) e o proprio GitHub confirmou que ela presta antes de ela ser guardada.\n\nO botao mora em /admin/caixa/robos/. Ao apertar, o site abre um pedido de mudanca no GitHub e a esteira o aprova sozinha, entao a tarefa some da fila em alguns minutos, e nao na hora.\n\nO QUE ISTO NAO PROVA: ninguem apertou o botao ainda. A prova de que ele funciona de ponta a ponta e apertar uma vez e ver a tarefa sumir.",
  autoridade: "mantenedor",
  evidencia: "Saida do infra/por-a-chave-do-github.sh colada por ele em 07/09/2026: '== PRONTO ==' com a linha da chave conferida dentro do container e a confirmacao do GitHub. De fora, na mesma hora: GET https://meshcraft.top/admin/caixa/robos/ responde 302 para o login (o cracha vem antes da tela, que e o desenho) e GET https://meshcraft.top/admin/healthz responde 200. O caminho da chave foi construido no PR https://github.com/abundanciabr/sitesdoreino/pull/1267 e o texto da tela no https://github.com/abundanciabr/sitesdoreino/pull/1308.",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica"
});})();
