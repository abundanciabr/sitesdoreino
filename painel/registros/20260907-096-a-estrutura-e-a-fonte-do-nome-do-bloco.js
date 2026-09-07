(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-096-a-estrutura-e-a-fonte-do-nome-do-bloco",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "O revisor pegou dois defeitos na porta de cursos antes de ela pousar, e o contrato foi emendado no mesmo dia",
  detalhe: "O robo revisor leu o PR da porta de cursos (1349) e achou dois defeitos: o nome de um modulo sumia em silencio quando a letra dele mudava de posicao, e a conferencia de 'algum aluno ja passou por esta aula?' rodava fora da transacao que apaga. Os dois foram consertados e provados por sabotagem.\n\nA regra mudou: a lista de modulos que voce cola e a fonte do nome de cada modulo (nulo nao mexe, texto grava, vazio apaga); a obra que nunca se sobrescreve e a das aulas. Como a prosa do contrato e pedra, entrou este segundo PR de contrato, so com essa emenda.",
  autoridade: "rito",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1359 (PR #1359), so contracts/, etiqueta contrato, emenda do PR 1351. Nascido do export do PR 1349 no commit 3ef2a9df. Freeze com o congelado e o codigo na mesma arvore: contrato/cursos PASS identico (1616 linhas) e seguranca PASS (17 operacoes). Suite da celula 735 passed, 5 sabotagens pegas. TAR-268.",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso"
});})();
