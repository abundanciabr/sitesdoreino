(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-074-o-pr-1106-fecha-porque-a-main-ja-tinha-feito",
  tipo: "nota",
  quando: "2026-09-06",
  titulo: "O PR #1106 fechou sem merge: outro PR ja tinha tirado o relatorio do ar",
  detalhe: "Voce pediu para destravar o PR #1106, que estava parado com conflito. Conferi antes de mexer, e o conflito era o sintoma, nao o problema: dois robos fizeram a MESMA tarefa em paralelo, e o irmao gemeo dele chegou primeiro. Tudo o que o #1106 propunha ja estava no ar: a pagina do relatorio da fundacao ja responde 404 para quem nao e admin, e o texto continua inteiro no editor para voce.\n\nMergear seria ativamente ruim: as duas versoes numeraram a migracao do banco com o mesmo numero (0008), e duas com o mesmo numero derrubariam a area de administracao na proxima subida.\n\nFechei o #1106 com a explicacao escrita la dentro. Nada se perdeu, e ele pode ser reaberto a qualquer momento.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1106 fechado, com o comentario que mostra a medicao item a item. Medido de fora: curl em https://meshcraft.top/docs/relatorio-da-fundacao respondeu HTTP 404. Na main: documentos/relatorio-da-fundacao.md ja tem publico: false, a migracao 0008_o_relatorio_da_fundacao_so_para_administradores.py ja existe (com 0009..0015 em cima dela) e os testes de 404 publico ja estao em services/admin/tests/test_relatorio_da_fundacao_no_banco.py.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
