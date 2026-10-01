(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260930-045-aceite-tecnico-tar-1010",
  tipo: "medicao",
  quando: "2026-09-30",
  titulo: "A TAR-1010 passou nos portões do repositório",
  detalhe: "O PR #2384 integrou a revisão 11feb416c87709d407d51716b1bdc78c7c8eb9a8 no commit 45b6a842b9b7827c63354a197c4407a5157b24ca. O pacote offline aprovado tinha SHA-256 AD173B8520AC2BBFC0A898414F59B7DDAF444194B8FBD1B6B68E77BF4DB9EB37. Os 10 arquivos de código e teste estão em ci/**; os outros 14 arquivos são 2 contratos, 9 eventos, 1 tarefa e 2 recibos obrigatórios do rito.\n\nA suíte focal, Black e validação da fila foram executadas no rito de entrega. O GitHub marcou os portões ci-celula-gate, muralhas, mandato e pouso como sucesso. O deploy admin também terminou publicado no run 36669638825, efeito incidental da esteira: esta medição aceita a revisão integrada no repositório e não afirma uma jornada funcional em produção.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2384 https://github.com/abundanciabr/sitesdoreino/actions/runs/36669638825 — ci/esperar.py --deploy 45b6a842b9b7827c63354a197c4407a5157b24ca --so-desfecho: deploy-celula success; ci/esperar.py --entrega 2384 --so-desfecho: PUBLICADO, jobs_sem_prova=[]. A conferência oficial do PR lista 24 arquivos (10 de ci/**, 2 contratos, 9 eventos, 1 tarefa e 2 recibos); os portões ci-celula-gate, muralhas, mandato e pouso ficaram SUCCESS. Comando focal do rito make pr: python -m pytest ci/tests/test_espera.py ci/tests/test_pr.py ci/tests/test_fila.py ci/tests/test_muralha_da_espera.py ci/tests/test_guarda_dos_guardas.py ci/tests/test_catraca_de_testes.py ci/tests/test_mergear.py ci/tests/test_contract_freeze.py -q; resultado registrado: PASS (exit 0). Black e fila também tiveram exit 0.",
  verificado_em: "2026-09-30",
  precisa_do_dono: false,
  responde_a: "20260930-038-ci-diagnosticos-vigentes",
  relacao: "comentario",
  tarefa: "TAR-1010",
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2384",
    revisao: "aa1d95c2224bcf1043b665416255995beb7fe44f",
    arvore: "8b424c73239d8489ff05297d7a5597f5645cd44d",
    integracao: "45b6a842b9b7827c63354a197c4407a5157b24ca",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36669638825"]
  },
  aceite_funcional: {
    resultado: "PASS",
    criterio: "Os diagnósticos vigentes apontam aos procedimentos atuais; o diff limita as alterações de comportamento a strings e ao teste causal autorizado; suíte focal, formatação e fila passam na revisão integrada.",
    evidencia: "Comando: python -m pytest ci/tests/test_espera.py ci/tests/test_pr.py ci/tests/test_fila.py ci/tests/test_muralha_da_espera.py ci/tests/test_guarda_dos_guardas.py ci/tests/test_catraca_de_testes.py ci/tests/test_mergear.py ci/tests/test_contract_freeze.py -q. Saída registrada no make pr: PASS (exit 0), tanto na validação da árvore quanto na do SHA final. Black 24.10.0 nos nove arquivos de produção e python ci/fila.py validar também tiveram exit 0. ci/esperar.py --entrega 2384 --so-desfecho retornou PUBLICADO e jobs_sem_prova=[]. O aceite funcional é da integração no repositório; não foi medida uma jornada de produção.",
    revisao: "45b6a842b9b7827c63354a197c4407a5157b24ca",
    comando: "python -m pytest ci/tests/test_espera.py ci/tests/test_pr.py ci/tests/test_fila.py ci/tests/test_muralha_da_espera.py ci/tests/test_guarda_dos_guardas.py ci/tests/test_catraca_de_testes.py ci/tests/test_mergear.py ci/tests/test_contract_freeze.py -q",
    ambiente: "repositorio-integrado"
  }
}); })();





