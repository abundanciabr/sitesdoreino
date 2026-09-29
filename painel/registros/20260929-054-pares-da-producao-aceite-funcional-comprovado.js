(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260929-054-pares-da-producao-aceite-funcional-comprovado",
  tipo: "medicao",
  quando: "2026-09-29",
  titulo: "Conexoes entre servicos: entrega e teste conferidos",
  detalhe: "Complementa o registro 047 com o aceite do lote TAR-989. Os 14 guardas foram exercitados em Linux isolado; a revisao integrada seguiu pela publicacao oficial. A verificacao em producao cobre o transporte do codigo, sem executar provisionadores de negocio na VPS. A frente PME08 e as TAR-986 e TAR-987 continuam pendentes.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/2355; https://github.com/abundanciabr/sitesdoreino/actions/runs/36617008179. 14/14 blobs dos scripts iguais entre a revisao testada e o commit integrado; teste de disputa real em Linux sem rede 1 passed; suite de exclusao comum 62 passed; revisao independente sem achados; quatro jobs exigidos do deploy-celula success.",
  verificado_em: "2026-09-29",
  precisa_do_dono: false,
  responde_a: "20260929-047-pares-da-producao-com-trava-comum-verificados",
  relacao: "comentario",
  tarefa: "TAR-989",
  gravidade: "verde",
  frente: "fabrica",
  area: "infra",
  aceite_funcional: {
    resultado: "PASS",
    criterio: "No lote TAR-989, os 14 scripts adquirem a mesma trava antes de mutar e a revisao integrada percorre a rota oficial de transporte ate a producao. A disputa foi exercitada em Linux isolado; os efeitos de negocio dos provisionadores nao foram executados na VPS.",
    evidencia: "14/14 blobs identicos entre 094f12d45300605428a7590a1b561f83847af260 e 53e90009b51cb4f176f1a933070ec73ed3904417; pytest ci/tests/test_exclusao_comum_da_publicacao.py: 62 passed; disputa real do provisionar-par-da-caixa.sh em Linux sem rede: 1 passed; revisao independente sem achados; https://github.com/abundanciabr/sitesdoreino/actions/runs/36617008179: detectar, portao-de-deploy, publicar-dados-admin e deploy (admin) success. Ambiente producao identifica somente o transporte oficial; o teste da exclusao ocorreu em Linux isolado.",
    revisao: "53e90009b51cb4f176f1a933070ec73ed3904417",
    ambiente: "producao"
  },
  entrega: {
    pr: "https://github.com/abundanciabr/sitesdoreino/pull/2355",
    revisao: "094f12d45300605428a7590a1b561f83847af260",
    arvore: "f7d117d8f447c371c64a71d2181cffeaae01c35a",
    integracao: "53e90009b51cb4f176f1a933070ec73ed3904417",
    publicacao: "PUBLICADO",
    publicacoes: ["https://github.com/abundanciabr/sitesdoreino/actions/runs/36617008179"]
  }
}); })();