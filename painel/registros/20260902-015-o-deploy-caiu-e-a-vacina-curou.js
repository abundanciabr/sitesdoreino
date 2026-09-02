(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-015-o-deploy-caiu-e-a-vacina-curou",
  tipo: "incidente",
  quando: "2026-09-02",
  titulo: "Uma entrega falhou por instabilidade do servidor, e o remédio automático resolveu",
  detalhe: "Enquanto as peças da escada subiam, uma entrega ficou vermelha: a parte da administração não conseguiu ser ativada no servidor. Três tentativas, todas recusadas na porta de entrada do servidor, com a mensagem de tempo esgotado.\n\nNão era defeito do que foi entregue nem do servidor: é uma instabilidade intermitente já conhecida e catalogada nesta casa, entre a máquina que publica e o servidor. O remédio automático mediu a porta do servidor, confirmou que ela responde e que o site estava de pé, e repetiu a entrega. Ficou verde na primeira repetição.\n\nUma segunda entrega, a da sua tela, tinha sido cancelada por disputa de vez entre duas publicações ao mesmo tempo. O mesmo remédio mediu e RECUSOU repetir, com razão: o que ela levava já estava no ar por uma publicação mais nova, e repetir teria devolvido o site a um estado mais velho. Isso é uma armadilha conhecida, e a ferramenta existe justamente para não cair nela.\n\nNada ficou pendente com você. Registro aqui porque a entrega ficou vermelha em algum momento, e o livro não esconde vermelho.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33639862193 — falhou com 'dial tcp ***:22: i/o timeout' nas 3 tentativas e ficou verde na repeticao pela vacina ci/rerun_de_deploy.py (armadilhas/127). O run cancelado 33640146894 foi diagnosticado e NAO repetido (armadilhas/188): a publicacao verde b340546f9019 ja continha o commit dele.",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
