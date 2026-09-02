(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-058-a-limpeza-dos-voltar-repetidos-chegou-no-ar",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "A limpeza dos \"voltar\" repetidos também chegou no ar",
  detalhe: "O PR #891 está em produção, e com ele a área de administração fechou o assunto do dia: menu e rodapé próprios em toda tela, e sem o link repetido no alto de cada uma.\n\nA prova, medida e não deduzida: a última publicação verde do servidor é a do commit b7d865b2, e ela contém tanto o commit do menu (a0d7c88e, PR #886) quanto o da limpeza (ff7f1e3c, PR #891). Conferido também de fora: o sinal de vida da área responde 200, /admin/ manda para o login como deve para quem não entrou, a biblioteca pública responde 200 e o site responde 200.\n\nOutra vez o deploy do próprio merge não foi o que entregou, e outra vez isso não é problema. A fila do servidor atende uma atualização por vez, e uma mais nova toma a vez da que estava esperando. A atualização que entrou no lugar levava a limpeza junto, então repetir a cancelada seria levar uma versão MAIS VELHA do site para o ar. Conferi essa conta antes de decidir, do jeito que armadilhas/188 manda: qual foi a última publicação verde, e se ela já contém o que eu queria publicar.\n\nA lição do dia virou armadilhas/292, e ela não é sobre deploy: é sobre teste. Dois guardas de telas que eu nem toquei ficaram vermelhos porque mediam a página INTEIRA para responder uma pergunta sobre um pedaço dela, e o menu novo no topo entrou no meio da medição. Passaram a medir o pedaço, com asserção mais apertada que a de antes.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33690525852",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
