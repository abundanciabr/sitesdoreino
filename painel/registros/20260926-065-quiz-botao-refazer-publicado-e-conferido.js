(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260926-065-quiz-botao-refazer-publicado-e-conferido",
  tipo: "medicao",
  quando: "2026-09-26",
  titulo: "Quiz: botao Refazer no ar e conferido",
  detalhe: "O resultado do Crivo tem o botao Refazer o quiz, que abre sessao nova sem apagar o envio antigo. No site, a rota recusa GET com 405 e POST sem token com 403.",
  autoridade: "sonda",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2122 MERGED 869d3361; https://github.com/abundanciabr/sitesdoreino/actions/runs/36274527935 success; https://meshcraft.top/quiz/crivo/ GET 200, /quiz/crivo/refazer GET 405, POST sem token 403.",
  verificado_em: "2026-09-26",
  precisa_do_dono: false,
  responde_a: "20260926-063-quiz-resultado-do-crivo-ganha-o-botao-refazer-o-quiz",
  relacao: "comentario",
  tarefa: "TAR-764",
  gravidade: "verde",
  frente: "vender",
  area: "quiz"
}); })();
