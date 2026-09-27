(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260927-015-appmax-url-publica-conferida",
  tipo: "medicao",
  quando: "2026-09-27",
  titulo: "Vista Appmax (TAR-730): URL conferida, tela logada sem ver",
  detalhe: "meshcraft.top/admin/appmax/ esta no ar: HTTP 302 para /entrar/google, porta fail-closed sem ADMIN_EMAILS. PR 2096 integrado, checks admin em PASS, exercitando os seis criterios do contrato por teste. Nao vi a tela autenticada: exige login Google que esta sessao nao tem nem deve buscar. Gesto para fechar: mantenedor abre a URL logado e confere os seis criterios.",
  autoridade: "sessao",
  evidencia: "PR github.com/abundanciabr/sitesdoreino/pull/2096; checks run 36238480062 PASS; curl -sI meshcraft.top/admin/appmax/ = 302 /entrar/google",
  verificado_em: "2026-09-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  area: "admin",
  tarefa: "TAR-730"
});})();
