(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260922-014-remocao-da-vigilia-colide-com-teste-fora-do-brief",
  tipo: "pendencia",
  quando: "2026-09-22",
  titulo: "A remoção da vigília colide com um teste fora do brief",
  detalhe: "No PR #1891, os cinco lançadores e o prompt foram removidos, e a nova prova focal passou com dois testes. Porém services/admin/tests/test_continuidade_local.py ainda importa o motor removido e agora termina em FileNotFoundError durante a coleta. O brief proíbe tocar em services/admin. Integrar este ramo nesse estado quebraria a suíte admin; o escopo precisa incluir a retirada desse teste obsoleto para a entrega ficar pronta.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1891",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null
}); })();
