(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260927-330-incidente-publicacao-do-admin-sem-pyyaml",
  tipo: "incidente",
  quando: "2026-09-27",
  titulo: "Os dados do painel do administrador ficaram 45 minutos sem publicar",
  detalhe: "O PR 2297 pôs import yaml no topo de ci/economia_da_fabrica.py. O job publicar-dados-admin importa esse arquivo sem PyYAML e reprovou em 4 deploys, de 23:00 a 23:45 UTC; o deploy do site admin passou em todos. O PR 2307 levou o import para dentro da leitura das fichas, com teste, e o deploy do merge d866ca4 passou inteiro. O mantenedor autorizou os dois PRs na sessão.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/36359599393",
  verificado_em: "2026-09-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null
}); })();
