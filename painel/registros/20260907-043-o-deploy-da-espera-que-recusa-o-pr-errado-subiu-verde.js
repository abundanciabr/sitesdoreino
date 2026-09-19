(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-043-o-deploy-da-espera-que-recusa-o-pr-errado-subiu-verde",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "O conserto da espera esta no ar, e a plataforma responde",
  detalhe: "O PR 1279 foi mergeado e o deploy da celula admin subiu verde em 57s.\n\nO primeiro disparo foi cancelado: nesta madrugada entrou um merge a cada 2 ou 3 minutos e os deploys se cancelaram uns aos outros, quatro em meia hora, de varios PRs. Nao houve causa no codigo, e a repeticao automatica resolveu sozinha, sem ninguem tocar.\n\nProva de fora, medida na internet publica depois do deploy: meshcraft.top responde 200 e /admin/painel/ responde 302, a porta fechada mandando para o login.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/34083913330",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
}); })();
