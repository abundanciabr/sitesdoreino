(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-104-a-porta-de-cursos-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "A sala de aula ja sabe criar cursos: a porta de cursos esta no ar, e o deploy terminou verde",
  detalhe: "A sala passou a aceitar varios cursos, cada um com o seu produto, a sua regra de avanco (por laudo, a do livro, ou livre) e a sua lista de modulos e aulas, tudo pela porta que o Admin usa. Os numeros de aula deixaram de ser so os do livro, e os blocos vao de A a Z.\n\nO codigo do PR 1349 pousou dentro do PR 1357 (o Guardiao de fidelidade, de outra sessao sua), porque os dois se travavam no contrato congelado; nada se perdeu. O revisor achou dois defeitos antes do pouso e os dois foram consertados e provados por sabotagem.\n\nFaltam, para o curso 1: a progressao livre (TAR-270) e a tela de colar as aulas (TAR-272), as duas em construcao.",
  autoridade: "sonda",
  evidencia: "deploy-celula 34152236740 (merge do PR https://github.com/abundanciabr/sitesdoreino/pull/1357, que carrega os commits do PR https://github.com/abundanciabr/sitesdoreino/pull/1349): completed, success, lido por gh run view --json. Suite da celula no PR: 776 passed em Postgres real. De fora: GET https://meshcraft.top/cursos/healthz 200. TAR-266 e TAR-268 concluidas.",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso"
});})();
