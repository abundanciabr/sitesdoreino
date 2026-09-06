(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-032-ninguem-e-aluno-do-site-e-aluno-de-um-curso",
  tipo: "decisao",
  quando: "2026-09-06",
  titulo: "Ninguem e aluno do site: todo mundo e aluno de UM CURSO",
  detalhe: "Voce mandou registrar como funciona daqui pra frente, e esta e a regra: a matricula passa a dizer DE QUAL CURSO a pessoa e aluna. Uma pessoa pode ter varias, uma por curso.\n\nPOR QUE ISSO IMPORTA AGORA: ate hoje ser aluno era sim ou nao, e a sala de aula servia 'o curso do site'. Com um curso so isso funcionava por coincidencia. No dia do segundo curso, TODO aluno veria o primeiro, sem erro e sem aviso.\n\nOS CURSOS: o 1 e Primeiros Dolares com Roblox, e e o de TODOS os alunos que ja estao no site. O 2 e o curso do livro, que esta sendo construido. Toda matricula que existe hoje passa a apontar para o 1, que e o unico desfecho verdadeiro: essas pessoas compraram aquele curso.\n\nO QUE MUDA NA SUA TELA: liberar deixa de ser um botao so. Passa a ser escolher o curso (obrigatorio, sem opcao ja marcada) e so entao liberar. Sem curso escolhido, nao libera.\n\nUMA BOA NOTICIA MEDIDA: metade disso ja existia. A matricula ja tem o campo do curso desde o primeiro dia, e quem entra COMPRANDO ja informa qual. O buraco era so quem entra pela sala de espera.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1174 (PR #1174), com docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md. Medido no origin/main: Matricula.product_id existe na primeira migracao da celula alunos; a restricao de unicidade da fila diz por escrito que varias matriculas por pessoa sao o normal, um curso cada; POST /matriculas exige product_id; e services.py cria a linha da fila com product_id vazio, que e o unico buraco. Tarefa TAR-220 na fila.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
