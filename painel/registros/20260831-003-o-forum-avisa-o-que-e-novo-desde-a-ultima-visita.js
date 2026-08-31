(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-003-o-forum-avisa-o-que-e-novo-desde-a-ultima-visita",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O fórum passou a avisar o que é novo desde a última visita",
  detalhe: "Entregue na noite de 30 para 31 de agosto, a tempo da inauguração.\n\nQuem entra no fórum agora vê, na capa, quantas conversas têm novidade em cada área. Dentro da área, cada conversa nova aparece marcada, e existe um botão \"Já vi tudo desta área\" para zerar quando você quiser. Abrir uma conversa já a marca como lida.\n\nÉ a peça que faz uma pessoa voltar todo dia: sem ela, o aluno abre o fórum e não sabe se tem algo novo, então relê a lista inteira ou simplesmente para de abrir.\n\nDuas coisas foram feitas com cuidado por baixo. A primeira: o fórum guarda UMA linha por pessoa por área (o \"li até aqui\"), mais as poucas exceções do que foi lido depois disso, e essas exceções são apagadas quando você marca tudo como lido. A forma ingênua, guardar uma linha para cada mensagem lida por cada pessoa, criaria milhões de linhas com 200 alunos, e o conserto depois seria caro. Existe teste medindo isso: trinta conversas abertas viram trinta linhas pequenas, e um clique devolve tudo a uma linha.\n\nA segunda: a conta compara com a última atividade da conversa, e não com a data em que você passou por ela. Sem isso, uma conversa que acabou de receber resposta continuaria parecendo lida, e o aviso falharia justamente quando havia novidade.\n\nVisitante não tem novidade nenhuma, e isso é de propósito: sem entrar, o fórum não tem de quem guardar essa marca.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/670 e o fecho em https://github.com/abundanciabr/sitesdoreino/pull/672 — 10 testes novos, suíte da célula 170 para 180 verdes, com vermelho na asserção contra o código anterior (9 failed / 1 passed); deploy-celula run 33344865619 completed/success nas duas células, lido por gh run view --json; prova de fora sem login: /forum/ e /forum/a/avisos em 200 com ZERO etiquetas de novidade e ZERO botões (visitante não tem marca), o estilo novo servido pelo site, e POST em /forum/a/avisos/li-tudo respondendo 403 sem crachá",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
