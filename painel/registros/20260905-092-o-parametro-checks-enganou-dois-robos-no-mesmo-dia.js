(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-092-o-parametro-checks-enganou-dois-robos-no-mesmo-dia",
  tipo: "nota",
  quando: "2026-09-05",
  titulo: "Dois robos passaram a quantidade de checks, nao o numero do PR, para o instrumento de espera",
  detalhe: "Medido hoje: um robo passou --checks 6 (a quantidade de checks que via) e o instrumento foi medir o PR #6, mesclado desde os primeiros dias e alheio a tarefa. Outro passou --checks 13 e mediu o PR #13, mesclado desde agosto. Nos dois casos o instrumento e fail-closed e recusou pousar o que nao conseguia medir, entao nada foi danificado, mas cada erro queimou o ciclo inteiro de 20 tentativas antes do robo perceber.\n\nCatalogado como armadilhas/354, com a regua: o argumento de --checks e o numero do PR (o mesmo de 'gh pr view' e da URL), nunca uma contagem. Aberta tambem a TAR-202 no balcao para o conserto de fundo (o instrumento recusar na hora um numero que nao e um PR aberto, com frase que ensine) — nao construida nesta entrega porque ci/ e caminho CODEOWNERS e nao havia mandato para toca-lo hoje.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1133",
  verificado_em: "2026-09-05",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
}); })();
