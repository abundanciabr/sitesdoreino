(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260929-071-aceite-da-barreira-da-coorte-piloto",
  tipo: "medicao",
  quando: "2026-09-29",
  titulo: "Aceite da barreira de reserva e pouso da coorte piloto",
  detalhe: "O incremento TAR-992 integrado e publicado faz claim, pausa e pouso disputarem a mesma barreira CAS nos ensaios de dois remotos bare. Resposta perdida conserva o efeito até desfecho terminal; cliente antigo, evento de nome genérico e arquivo 101º são recusados no receptor de merge, enquanto PR fora da coorte segue. O manifesto continua inativo: este aceite não comprova transferência Git para PostgreSQL nem reivindicação real da TAR-994.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2358 https://github.com/abundanciabr/sitesdoreino/actions/runs/36631635347 — ci/esperar.py --entrega 2358 --so-desfecho: PUBLICADO, integracao 2db356a80608fee430ba48528e09489005498189, jobs_sem_prova []; git diff --exit-code 79157893899f59edb403b70fa0a679ca32dbab07 2db356a80608fee430ba48528e09489005498189 -- oito alvos I1: exit 0; python -m pytest -q ci/tests/test_reservar.py ci/tests/test_mergear.py ci/tests/test_fila.py -k 'claim_piloto or cliente_antigo or pouso_e_pausa or pouso_recupera or pouso_recusa_pr_piloto or pouso_reconhece_evento or pouso_recusa_evento_generico or pouso_reconhece_tarefa_piloto_em_arquivo or pouso_encontra_evento_piloto_na_segunda or pouso_recusa_lista_paginada or pouso_falha_fechado_se_api or pouso_reconhece_tarefa_piloto_so_no_corpo or pouso_nao_consulta_barreira or pouso_reconsulta_barreira or pouso_adquire_efeito or pouso_incerto_conserva or pouso_alheio_a_coorte or pista_reconcilia_efeito': 29 passed, 456 deselected. Revisor independente: 27 PASS em hashes congelados. Nenhuma ref piloto real ativada.",
  verificado_em: "2026-09-29",
  precisa_do_dono: false,
  responde_a: "20260929-068-barreira-cas-da-coorte-piloto-tar-992",
  relacao: "comentario",
  tarefa: "TAR-992",
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2358",
    revisao: "23bdf67c7e43f856861adef5032e0cb872a53d4b",
    arvore: "40f7b0ed26b8512cd8e4f367be3fbe721187aec6",
    integracao: "2db356a80608fee430ba48528e09489005498189",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36631635347"]
  },
  aceite_funcional: {
    resultado: "PASS",
    criterio: "Duas corridas reais de claim e pausa em remoto bare têm vencedor único; pouso disputa a mesma barreira antes do merge; resposta incerta permanece bloqueada; cliente antigo não integra evento piloto após pausa; tarefa alheia conserva fluxo Git. Código idêntico na integração publicada. O manifesto não é ativado neste incremento.",
    evidencia: "Prova focal pós-integração: 29 passed, 456 deselected em ci/tests/test_reservar.py, test_mergear.py e test_fila.py; negativos para cliente antigo, nome genérico, arquivo 101º, resposta incerta e PR não piloto. git diff --exit-code entre 79157893899f59edb403b70fa0a679ca32dbab07 e 2db356a80608fee430ba48528e09489005498189 nos oito alvos I1: exit 0. ci/esperar.py --entrega 2358: PUBLICADO no run 36631635347, jobs_sem_prova []. Sem claim real ou corte PG.",
    revisao: "2db356a80608fee430ba48528e09489005498189",
    ambiente: "producao"
  },
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
