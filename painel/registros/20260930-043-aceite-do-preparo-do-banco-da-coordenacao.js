(function(){ (window.REGISTROS = window.REGISTROS || []).push(
{
  "arquivo": "20260930-043-aceite-do-preparo-do-banco-da-coordenacao",
  "tipo": "medicao",
  "quando": "2026-09-30",
  "titulo": "Aceite do preparo do banco da coordenação",
  "detalhe": "A correção do Compose integrada foi publicada e o provisionamento oficial preparou o banco e esquema nominais, conservando as identidades novas sem acesso.",
  "autoridade": "sessao",
  "evidencia": "PR #2372 integrado em 3c0ef99; ci/esperar.py --entrega 2372 --so-desfecho: PUBLICADO em https://github.com/abundanciabr/sitesdoreino/actions/runs/36652634784, jobs_sem_prova []. Imagem e dados admin na revisão 64a280e5 publicados em https://github.com/abundanciabr/sitesdoreino/actions/runs/36667241802; saúde/imagem observadas em https://github.com/abundanciabr/sitesdoreino/actions/runs/36667795491. A correção do provisionador no PR https://github.com/abundanciabr/sitesdoreino/pull/2382 antecedeu a jornada específica TAR-1004 em provisionar.yml https://github.com/abundanciabr/sitesdoreino/actions/runs/36667286386 em 64a280e5 SUCCESS: `PRONTO: banco e esquema da coordenação preparados; identidades novas seguem sem acesso.`; etapa automática de prova confirmou. Backup externo é prova separada e não integra este aceite.",
  "verificado_em": "2026-09-30",
  "precisa_do_dono": false,
  "responde_a": null,
  "relacao": "comentario",
  "tarefa": "TAR-1004",
  "gravidade": "verde",
  "frente": "fabrica",
  "area": "infra",
  "entrega": {
    "pr": "https://github.com/abundanciabr/sitesdoreino/pull/2372",
    "revisao": "209eee51e11f4d60638524750a449eeb7818d43e",
    "arvore": "970ddb640ba5f5ff53f6b24db216bde7b4f9ea83",
    "integracao": "3c0ef9935fcc2d2acb01359117f6bae687e2f473",
    "publicacao": "PUBLICADO",
    "publicacoes": [
      "https://github.com/abundanciabr/sitesdoreino/actions/runs/36652634784",
      "https://github.com/abundanciabr/sitesdoreino/actions/runs/36667241802",
      "https://github.com/abundanciabr/sitesdoreino/actions/runs/36667795491"
    ]
  },
  "aceite_funcional": {
    "resultado": "PASS",
    "criterio": "Preparo oficial termina PRONTO, banco e esquema nominais conferidos, Compose real aceita ambiente, identidades sem acesso, nenhum segredo publicado.",
    "evidencia": "Código TAR-1004 integrado em 3c0ef9935fcc2d2acb01359117f6bae687e2f473 e publicado em https://github.com/abundanciabr/sitesdoreino/actions/runs/36652634784. Imagem admin observada na revisão 64a280e5f0590c0788cb4d5f02cfae36f02c0f6e; dados admin da revisão 64a280e5f0590c0788cb4d5f02cfae36f02c0f6e publicados em https://github.com/abundanciabr/sitesdoreino/actions/runs/36667241802 e imagem/saúde medidas em https://github.com/abundanciabr/sitesdoreino/actions/runs/36667795491. Esse run de medição verifica imagem/saúde, não banco. A correção do provisionador no PR https://github.com/abundanciabr/sitesdoreino/pull/2382 antecedeu a observação funcional específica TAR-1004 em provisionar.yml https://github.com/abundanciabr/sitesdoreino/actions/runs/36667286386 em 64a280e5f0590c0788cb4d5f02cfae36f02c0f6e: SUCCESS, `PRONTO: banco e esquema da coordenação preparados; identidades novas seguem sem acesso.`, com etapa automática de prova verde. Testes Compose real vermelho/verde e FD8 da entrega #2372.",
    "revisao": "64a280e5f0590c0788cb4d5f02cfae36f02c0f6e",
    "ambiente": "producao",
    "publicacao_efetiva": {
      "run_imagem": "https://github.com/abundanciabr/sitesdoreino/actions/runs/36667241802",
      "run_dados": "https://github.com/abundanciabr/sitesdoreino/actions/runs/36667241802",
      "run_medicao": "https://github.com/abundanciabr/sitesdoreino/actions/runs/36667795491",
      "revisao_dados": "64a280e5f0590c0788cb4d5f02cfae36f02c0f6e"
    }
  },
  "vence_em_dias": null,
  "se_eu_nao_decidir": null,
  "recomendacao": null,
  "reversivel": null
}
); })();
