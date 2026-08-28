(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-071-o-portao-parou-de-dizer-verde-e-falhar-em-seguida",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O portão parou de dizer verde e falhar logo em seguida",
  detalhe: "A trava que liguei hoje de manhã abriu uma lacuna sem querer, e ela acabou de ser fechada.\n\nO portão que confere se uma entrega pode ser aprovada dizia VERDE quando a entrega estava desatualizada em relação à versão oficial. Aí o robô mandava aprovar, e o GitHub recusava na hora seguinte: 'a entrega não está em dia com a base'. Verde na tela e recusa na hora de agir é a pior combinação que existe aqui — o robô acredita no portão, não no GitHub.\n\nAgora o portão recusa antes, e explica o que fazer: atualizar a entrega, esperar os testes rodarem de novo contra o mundo novo, e só então aprovar.\n\nE ele avisa de uma pegadinha que me custou uma rodada inteira hoje: ao atualizar, o painel gerado fica velho em relação aos registros que vieram junto, e o teste do painel reprova. O aviso agora está escrito no próprio portão, para o próximo robô não descobrir do jeito caro.\n\nIsso não elimina o trabalho extra de atualizar — só para de confundir quem está tentando. Quem elimina de verdade é a pista de pouso, que é a próxima onda e depende de uma coisa sua (está no registro seguinte).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/421. Medido no PR 414: o portao dizia 'PASS sem conflitos (BEHIND)' e o gh pr merge seguinte falhou com 'the head branch is not up to date with the base branch'. Suite ci/tests/test_mergear.py: 57 verdes. Prova por sabotagem: desligar a recusa do BEHIND => 2 vermelhos; restaurado => 57 verdes.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
