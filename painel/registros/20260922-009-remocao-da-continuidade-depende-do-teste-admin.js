(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260922-009-remocao-da-continuidade-depende-do-teste-admin",
  tipo: "pendencia",
  quando: "2026-09-22",
  titulo: "A remoção da continuidade depende de um teste fora do escopo",
  detalhe: "O teste services/admin/tests/test_continuidade_local.py exige novas sessões e importa o motor na coleta. Remover ou tornar o motor inerte quebra esse contrato. O despacho proíbe editar services/admin. Nenhum código foi alterado. A coordenação precisa incluir esse teste na remoção e medir a suíte admin. O baseline focal encontrou quatro ERROR por fixture db ausente, em e9f29af9e0911191d4f08fc0ed7a22e9fd279a21. O prazo de execução depende dessa correção do escopo e do ambiente.",
  autoridade: "sessao",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null
}); })();
