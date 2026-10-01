(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260929-051-ci-aceite-funcional-do-catalogo",
  tipo: "medicao",
  quando: "2026-09-29",
  titulo: "Aceite funcional do catalogo de tarefas",
  detalhe: "TAR-988: reuso de digests por coleta com conferência final e invalidação de fontes. Recorte real: 26,075 s antes e 13,452 s depois; catálogo completo de 878 tarefas em 89,439 s no Windows. O teto de 10 vezes não foi demonstrado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2353 e https://github.com/abundanciabr/sitesdoreino/actions/runs/36619214819. Quatro blobs do corte iguais em HEAD f05de545bec717fff95e9ed8fc7559c67b8c5205 e merge 1ff7745e493036e095abeeb7ce4fccab0f710586. Ensaio focal: 3 passed in 2.64s. Publicador: ADMIN-DADOS-PUBLICADOS tipo=fila sha=1ff7745e493036e095abeeb7ce4fccab0f710586 run=1920. A tela lê estados.json da publicação; não há leitura direta de mapa-de-execucao.json na aplicação.",
  verificado_em: "2026-09-29",
  precisa_do_dono: false,
  responde_a: null,
  relacao: "comentario",
  tarefa: "TAR-988",
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  aceite_funcional: {
    resultado: "PASS",
    criterio: "Gerar catálogo sem repetir digests por tarefa, preservar a invalidação e ativar a fila produzida pela revisão integrada.",
    evidencia: "No código integrado (blobs idênticos), python -m pytest ci/tests/test_mapa_de_execucao.py::test_catalogo_calcula_digest_da_fila_so_na_abertura_e_no_fecho ci/tests/test_mapa_de_execucao.py::test_catalogo_recusa_mecanismo_alterado_entre_pacotes ci/tests/test_mapa_de_execucao.py::test_catalogo_recusa_fila_que_muda_entre_leitura_e_digest -q -p no:cacheprovider: 3 passed in 2.64s. Em produção, deploy-celula executou python ci/preparar_dados_admin.py fila e publicou manifesto íntegro: ADMIN-DADOS-PUBLICADOS tipo=fila sha=1ff7745e493036e095abeeb7ce4fccab0f710586 run=1920 ativo=/opt/plataforma/admin-dados/fila_1920_1ff7745e493036e095abeeb7ce4fccab0f710586. O JSON do catálogo não possui leitor direto na tela.",
    revisao: "1ff7745e493036e095abeeb7ce4fccab0f710586",
    ambiente: "producao"
  },
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2353",
    revisao: "84ebea913bfe6969c975f654bf199f1adf75c859",
    arvore: "602e5fc7e00c1c789a8c3e8ec0f51415a47bd069",
    integracao: "1ff7745e493036e095abeeb7ce4fccab0f710586",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36619214819"]
  }
}); })();