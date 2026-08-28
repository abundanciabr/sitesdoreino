(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-069-ex-aluno-deixou-de-ser-um-sumico",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "Quem sai da escola passou a ouvir isso da home — e o botão de apagar avisa que não é a mesma coisa",
  detalhe: "Dois trabalhos do mesmo assunto, feitos por outra sessão, que ainda não tinham sido contados aqui. Registro por dívida do livro — quem escreveu foi outro robô, e eu conto pelo que os pedidos de mudança dizem.\n\nNA HOME, QUEM SAIU PASSOU A SABER QUE SAIU. Até agora, ex-aluno e pausado voltavam da parte que guarda os alunos como se fossem gente que nunca entrou — e a home não tinha o que dizer. A pessoa perdia o acesso e a tela fingia que ela nunca tinha estudado ali. Agora são duas frases diferentes: para quem saiu, que o acesso foi encerrado e ela fale com a escola se achar que houve engano; para quem está pausado, que o acesso volta assim que a equipe religar. A palavra que importa na segunda é VOLTA — a pessoa precisa saber que não tem nada a fazer.\n\nNENHUMA DAS DUAS CONVIDA A PEDIR DE NOVO, e isso é escolha: quem saiu ou foi pausado não está numa fila, está numa decisão da escola. Convidar a insistir contra uma decisão que a pessoa não conhece é pior que o silêncio.\n\nNO ADMIN, O BOTÃO DE APAGAR PAROU DE PARECER O DE EX-ALUNO. Você clicou em APAGAR querendo ex-aluno: os dois estavam lado a lado e a tela não dizia que faziam coisas diferentes. A ficha sumiu, e ela não volta. Agora o estado se chama \"Ex-aluno — perde o acesso, e a ficha continua aqui\", e o aviso do apagar diz ANTES da confirmação que apagar não é a mesma coisa: ex-aluno tira o acesso e a ficha fica, com tudo que a pessoa preencheu, e voltar é um clique; apagar some com a ficha, sem desfazer.",
  autoridade: "github",
  evidencia: "PRs https://github.com/abundanciabr/sitesdoreino/pull/403 (a home) e https://github.com/abundanciabr/sitesdoreino/pull/404 (o Admin), os dois mergeados. Provas declaradas nos pedidos: services/funil 354/354 com black limpo e mutação de ex-aluno voltando a não ver nada dando 2 vermelhos; services/admin 189/189 em Postgres com black limpo, e teste afirmando que o valor guardado no banco NÃO mudou com a troca de rótulo. Registro escrito por outra sessão que a dos autores, a partir do que os pedidos de mudança declaram — não conferi essas suítes de novo.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null
});})();
