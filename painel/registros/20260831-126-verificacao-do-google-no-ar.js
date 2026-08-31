(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-126-verificacao-do-google-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O codigo do Google Search Console ja esta no ar, pode voltar la e clicar em verificar",
  detalhe: "O PR #795 pousou, o deploy da celula que responde pela pagina inicial (funil) terminou verde, e conferi de fora: https://meshcraft.top/google0e78b54775677e95.html responde 200 com exatamente o texto que o Google pede.\n\nPROXIMO PASSO SEU: volte ao Google Search Console (a tela onde voce pegou esse codigo) e clique no botao de verificar propriedade. Ele deve confirmar na hora, porque o arquivo ja esta no lugar certo.",
  autoridade: "github",
  evidencia: "Merge: https://github.com/abundanciabr/sitesdoreino/pull/795 (sha 46c6a97f1c7331f12b29778f0507282e5a695fa7). Deploy CONFERIDO PELO VEREDITO REAL (gh run view --json status,conclusion, nunca por pipe): run 33448394076, status=completed, conclusion=success, 3min07s. Prova de fora depois do deploy: curl -i https://meshcraft.top/google0e78b54775677e95.html respondeu HTTP/1.1 200 OK, Content-Type text/plain, corpo exato 'google-site-verification: google0e78b54775677e95.html'.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-121-verificacao-do-google-search-console",
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
