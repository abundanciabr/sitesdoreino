(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-125-a-area-de-documentos-esta-no-ar-com-as-duas-portas",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A area de documentos do site esta no ar — uns publicos, outros so para voce",
  detalhe: "VOCE PEDIU e esta no ar, com as duas visibilidades que voce quis.\n\nMEshcraft.top/docs/ — ABERTO A QUALQUER PESSOA. Hoje tem um documento: 'Como funciona a entrada na escola', escrito para o ALUNO — o que acontece entre entrar com o Google e poder participar, os dois desfechos do pedido, o que cada situacao quer dizer, e o que a escola guarda sobre ele.\n\nMEshcraft.top/admin/documentos/ — SO PARA VOCE. Mostra TODOS, com a etiqueta de quem pode ler cada um. Ali esta tambem 'A jornada do aluno', o mapa que voce pediu: as oito paradas, as doze passagens, onde voce mexe em cada uma. Ele NAO e publico porque e escrito para quem administra — fala de painel, de fila e de gestao. A escolha nao e sobre segredo, e sobre a quem o texto serve.\n\nO PROPRIO DOCUMENTO DIZ QUEM PODE LE-LO: uma linha no topo do arquivo. Se essa linha faltar, ou estiver escrita de outro jeito, o documento fica PRIVADO. Nada escapa para o site aberto por esquecimento.\n\nO DOCUMENTO DA JORNADA NAO TRAZ NUMERO NENHUM, de proposito. Quantas pessoas estao em cada ponto e uma pergunta viva, e ela tem tela propria (/admin/escola/jornada/). Numero escrito num documento vira mentira no dia seguinte.\n\nCONFERIDO DE FORA, depois do deploy: a lista publica abre (200), o documento do aluno abre (200), o da jornada da 404 pelo endereco publico, um endereco inventado da 404 igual (de fora, um documento privado e um endereco que nao existe sao a mesma coisa), e a area de dentro pede cracha (302).",
  autoridade: "github",
  evidencia: "PRs #544 (a area), #550 (o endereco publico deixa de carregar o /admin) e #560 (o cadeado do roteador). Medicao de fora depois do deploy: GET meshcraft.top/docs/ = 200 com X-Frame SAMEORIGIN (a cadeia da celula admin, provando quem respondeu); /docs/como-funciona-a-entrada = 200 e o titulo renderizado; /docs/jornada-do-aluno = 404; /docs/nao-existe = 404; /admin/documentos/ sem cracha = 302; e a lista publica NAO contem a palavra 'jornada' (zero ocorrencias — o titulo do privado nao vaza). 42 guardas novos na celula admin, entre eles test_so_a_palavra_true_torna_um_documento_publico (oito jeitos plausiveis de escrever 'sim', e nenhum publica) e test_html_dentro_do_documento_sai_escapado.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
