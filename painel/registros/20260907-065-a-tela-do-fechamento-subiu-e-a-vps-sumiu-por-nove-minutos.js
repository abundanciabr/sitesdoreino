(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-065-a-tela-do-fechamento-subiu-e-a-vps-sumiu-por-nove-minutos",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "A tela do fechamento do ciclo subiu, e a VPS sumiu logo depois sem derrubar nada",
  detalhe: "O degrau 13 subiu com deploy verde. A tela existe em /admin/placar/fechamento/, e quem abre ela e voce: eu nao tenho cracha.\n\nMinutos depois, o deploy seguinte falhou porque a VPS parou de atender: tres tentativas de entrega e nenhuma medicao da porta. NINGUEM FICOU FORA DO AR, e isso nao e otimismo meu, e o que o proprio deploy escreveu: 'NADA FOI PUBLICADO, o site continua na versao ANTERIOR, sao'. Medi o site no meio do problema e ele respondia normal.\n\nA vacina do deploy refez sozinha e a segunda tentativa passou em 47 segundos. Nenhuma mao humana entrou nisso.\n\nO que carregava o deploy que falhou era so escrituracao (uma armadilha e um registro), nada que mudasse o site.",
  autoridade: "github",
  evidencia: "Veredito por gh run view --json, nunca por cano. Degrau 13 (PR 1327): run 34132151556 completed/success em 3min36s. O run seguinte 34132836336 falhou na tentativa 1 no passo 'Ativar na VPS (tentativa 3 de 3)' com R1/R2/R3 failure e a porta 22 em 'nao_medi'; a vacina abriu a tentativa 2, lida por gh api .../attempts/2/jobs, com deploy (admin) completed/success, e o run fechou completed/success. Site medido durante a falha: / 200, /forum 301, /admin/placar/ 302.",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica"
}); })();
