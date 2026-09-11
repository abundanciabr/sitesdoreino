(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260909-084-guardas-do-staging-do-admin-atualizados",
  tipo: "nota",
  quando: "2026-09-09",
  titulo: "Guardas do staging do admin atualizados",
  detalhe: "Os guardas passaram a reconhecer somente PAINEL_STAGING e FILA_STAGING e a validar o envio separado do payload de painel e fila para a VPS. O arquivo afetado passou em 22 testes; a suíte ampla terminou com 2196 aprovados, 183 falhas e 11 ignorados por problemas externos a esta correção.",
  autoridade: "sessao",
  evidencia: "python -m pytest ci/tests/test_backup_antes_da_migracao.py -q: 22 passed in 0.91s. A suíte ampla terminou com 2196 passed, 183 failed, 11 skipped em 918.77s.",
  verificado_em: "2026-09-09",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,
  se_eu_nao_decidir: "As falhas externas continuam impedindo o veredito verde da suíte completa.",
  recomendacao: "Corrigir os registros inválidos do painel e preparar o ambiente Bash/WSL antes de usar a suíte ampla como veredito.",
  reversivel: true
}); })();
