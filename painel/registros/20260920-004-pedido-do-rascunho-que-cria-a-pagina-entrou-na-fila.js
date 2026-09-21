(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260920-004-pedido-do-rascunho-que-cria-a-pagina-entrou-na-fila",
  tipo: "nota",
  quando: "2026-09-20",
  titulo: "O pedido de fazer salvar criar a pagina virou tarefa na fila, com as nove condicoes do mantenedor",
  detalhe: "Decisao dele em 20/09/2026: salvar o primeiro rascunho cria a pagina, sem semeador nem workflow manual. A tarefa 526 nasce aberta; este PR nao a conclui. Motivo medido: curl -I meshcraft.top/oferta devolve 404 com Server uvicorn, porque nao ha linha de pagina no catalogo e put_page_draft recusa antes de criar (api.py:136 e :263). O contrato ja declara esse 404 so para site inexistente, entao contracts/ nao muda.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1793",
  verificado_em: "2026-09-20",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "vender",
  area: "fila",
  vence_em_dias: null
});})();
