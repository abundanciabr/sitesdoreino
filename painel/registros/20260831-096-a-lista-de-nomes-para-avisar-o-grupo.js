(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-096-a-lista-de-nomes-para-avisar-o-grupo",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "No cartao 'Alunos ativos', um link com so os nomes de quem ja pode entrar",
  detalhe: "Voce pediu: uma lista dos nomes dos alunos ja aprovados, acessivel a partir de 'Alunos ativos', para voce avisar o grupo de quem ja foi liberado. E que essa lista tivesse SO o nome completo de cada um, nada mais.\n\nEsta ali agora. Na tela /admin/escola/alunos/, o cartao 'Alunos ativos' ganhou um link 'Ver os nomes para avisar o grupo'. Ele abre uma pagina com uma caixa de texto contendo cada nome completo numa linha, e nada mais: sem e-mail, sem WhatsApp, sem turma, sem nenhum rotulo. E so tocar e segurar (ou Ctrl+A no computador) para selecionar tudo e colar direto onde voce for avisar.\n\nOS NOMES VEM ORDENADOS alfabeticamente (ignorando acento e maiuscula/minuscula), para ficar facil de conferir de relance. E se, por coincidencia, dois alunos tiverem o mesmo nome, os dois aparecem: a lista conta matriculas, nao nomes unicos.\n\nA MESMA HONESTIDADE do resto dessa tela: se por algum motivo esta area nao conseguir perguntar para a parte que guarda os alunos, a pagina diz isso claramente, em vez de mostrar uma lista vazia que voce leria como 'ninguem foi liberado ainda' quando a verdade seria 'nao consegui nem perguntar'.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/770. 534 testes verdes na celula admin (15 novos so para esta tela), incluindo o teste de que o link mora dentro do cartao certo e o teste de que a lista nao vaza e-mail, WhatsApp ou turma. `black --check` limpo.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
