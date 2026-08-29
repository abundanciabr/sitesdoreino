(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-096-o-portao-barrou-um-deploy-por-causa-de-outro-e-quase-passou-batido",
  tipo: "nota",
  quando: "2026-08-29",
  titulo: "Uma publicação foi barrada por causa de OUTRA, e isso quase passou batido",
  detalhe: "Achado durante o conserto do endereço com \"www.\", e vale guardar porque é o tipo de coisa que morde em silêncio.\n\nAquele merge disparou DUAS publicações: a da infraestrutura e a do painel. A da infraestrutura falhou por instabilidade de conexão e eu a curei — ficou verde. Só que a do painel também tinha ficado vermelha, e por um motivo diferente: existe um portão que se recusa a publicar enquanto enxergar QUALQUER outra publicação vermelha em volta. Ele barrou a do painel por causa da da infraestrutura.\n\nCurar a primeira não desbloqueia a segunda. O portão barrou, e barrado ficou.\n\nPOR QUE QUASE PASSOU BATIDO: um merge seguinte, minutos depois, disparou uma publicação nova do painel, que passou limpa e publicou tudo. O resultado final ficou certo — mas por acidente de movimento, não porque alguém cuidou. Se aquele merge tivesse sido o último do dia, o painel teria dormido numa versão velha sem ninguém saber.\n\nA REGRA QUE FICA: merge que dispara duas publicações exige conferir as DUAS, mesmo quando a primeira que você olhou ficou verde. Guardei em armadilhas/178, com a linha exata do log que nomeia o culpado — assim o próximo robô não perde tempo achando que é defeito do próprio trabalho.\n\nNada ficou quebrado: conferi as duas publicações verdes e o site medido de fora.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/502",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
