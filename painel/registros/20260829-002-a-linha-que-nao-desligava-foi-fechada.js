(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-002-a-linha-que-nao-desligava-foi-fechada",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O servidor parou de abrir uma linha nova com o banco a cada visita",
  detalhe: "Havia um vazamento silencioso: cada visita abria uma conexão nova com o banco de dados e ela não era devolvida. Foi conferido no código instalado de verdade, e o alcance ficou menor do que o diagnóstico original dizia — era UMA parte do sistema, a que cuida do login, e não todas.\n\nAgora essa parte usa um conjunto fixo de linhas reaproveitadas, com teto. Guardas novos travam o conserto no lugar.\n\nEste registro paga uma dívida do livro: o PR entrou na main e ninguém tinha contado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/422 (MERGED, commit a0783a21a070, conferido com gh pr view em 28/08/2026)",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260827-036-o-servidor-abre-uma-linha-nova-a-cada-visita",
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
