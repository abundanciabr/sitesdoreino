(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260924-041-rota-flp-publicada-sem-conteudo",
  tipo: "entrega",
  quando: "2026-09-24",
  titulo: "Rota pública FLP implantada; ainda sem conteúdo publicado",
  detalhe: "O funil já responde por /flp-0 e só exibe uma versão publicada do catálogo. A borda pública respondeu HTTP 404 em 24/09/2026 porque nenhuma versão da FLP foi publicada. O deploy do funil terminou com sucesso.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2045 integrado em ca6585bdeaa9837bec3344d122092bc0f599dce4; https://github.com/abundanciabr/sitesdoreino/actions/runs/36026109182 concluído com sucesso; curl.exe -sS -D - -o NUL https://meshcraft.top/flp-0 retornou HTTP/1.1 404 Not Found.",
  verificado_em: "2026-09-24",
  precisa_do_dono: false,
  responde_a: "20260924-038-funil-rota-publica-flp-0",
  tarefa: "TAR-692",
  gravidade: "verde",
  frente: "site",
  area: "funil"
}); })();
