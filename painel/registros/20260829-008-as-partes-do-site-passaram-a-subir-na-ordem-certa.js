(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-008-as-partes-do-site-passaram-a-subir-na-ordem-certa",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "Quando várias partes do site mudam juntas, elas passam a subir na ordem certa",
  detalhe: "O site é feito de partes que conversam entre si: a tela de compra pergunta o preço para o catálogo, o painel pergunta quem é você para o login, e assim por diante. Quando uma entrega mexia em duas partes ao mesmo tempo, elas subiam em ordem alfabética — ou seja, no sorteio.\n\nO estrago disso é silencioso: quem pergunta subia antes de quem responde, e por alguns minutos o site ficava no ar respondendo errado, sem nada apitar. Não é erro que apareça em tela vermelha; é usuário mal atendido durante a janela.\n\nAgora a esteira descobre sozinha quem depende de quem — lendo o próprio código, não uma lista que alguém teria de manter — e sobe primeiro quem responde, depois quem pergunta. A explicação aparece no registro da entrega, em português: \"1. catálogo, 2. pagamentos, 3. tela de compra (depende dos dois)\".\n\nSe algum dia duas partes dependerem uma da outra em círculo, ela não trava a entrega nem escolhe escondido: escolhe e avisa quais são, para alguém arrumar a arquitetura com calma.\n\nSegunda metade da Onda 4, fatia 2.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/439",
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
