(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-065-a-tela-do-fechamento-subiu-e-a-vps-sumiu-por-nove-minutos",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "A tela do fechamento do ciclo subiu, e a VPS sumiu logo depois sem derrubar nada",
  detalhe: "O degrau 13 subiu com deploy verde. A tela existe em /admin/placar/fechamento/, e quem abre e voce: eu nao tenho cracha.\n\nMinutos depois, o deploy seguinte falhou porque a VPS parou de atender. NINGUEM FICOU FORA DO AR, e isso e o que o proprio deploy escreveu: 'NADA FOI PUBLICADO, o site continua na versao ANTERIOR, sao'. Medi o site no meio do problema e ele respondia normal.\n\nA vacina refez sozinha e passou em 47 segundos. Nenhuma mao humana entrou nisso, e o que o deploy falho carregava era so escrituracao.",
  autoridade: "github",
  evidencia: "Degrau 13 (PR 1327): run 34132151556 completed/success em 3min36s, por gh run view --json. O run 34132836336 falhou na tentativa 1 em 'Ativar na VPS', com a porta 22 em 'nao_medi'; a tentativa 2, lida por gh api .../attempts/2/jobs (armadilhas/307), deu completed/success. Site durante a falha: / 200, /forum 301, /admin/placar/ 302. PR deste registro: https://github.com/abundanciabr/sitesdoreino/pull/1330",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica"
}); })();
