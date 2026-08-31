(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-107-a-caixa-explica-as-etapas",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A Caixa de Sugestões passa a explicar ao aluno o que cada etapa quer dizer",
  detalhe: "Você abriu a linha do tempo de uma ideia, viu \"Em análise\" e perguntou se aquilo não deveria se chamar \"Em votação\", para incentivar os alunos a votar. A pergunta destapou um buraco maior que o nome: a Caixa desenhava quatro etapas em DUAS telas (a linha do tempo da ideia e a faixa de roadmap do quadro) e nenhuma das duas dizia o que elas significam.\n\nSua decisão, no mesmo dia: o nome continua \"Em análise\", o voto continua aberto em qualquer etapa, e a Caixa passa a explicar.\n\nO que o aluno vê agora. Na página da ideia, logo abaixo do selo, uma frase dizendo o que a situação daquela ideia quer dizer, sempre visível (inclusive nas duas que não têm bolinha na linha do tempo, \"Não planejado\" e \"Mesclado\", que é onde a pessoa mais precisa de uma explicação). Nas duas telas, um bloco \"O que cada etapa quer dizer\" que abre no clique. E a frase que faltava: votar nunca fecha, dá para votar numa ideia em qualquer etapa, e é na primeira que o voto decide se ela entra. Essa última descreve o código que já existia: o botão de votar nunca olhou a etapa, e nenhuma tela dizia isso.\n\nOs textos moram num lugar só, e as duas telas leem de lá. Copiar a frase num template reprova no teste, porque no HTML pronto o texto vindo do código e o copiado à mão são idênticos, e é isso que faz a cópia envelhecer sem ninguém ver.\n\nUm buraco apareceu no caminho e ficou anotado, não consertado: o portão que caça travessão no texto publicado não olha arquivos de código, e os nomes das etapas (\"Em análise\" e os outros cinco) sempre foram texto que o aluno lê, morando em código. Consertar isso mexe em pasta que exige sua autorização, então virou a armadilha 254 e a tarefa TAR-087 na fila, com um guarda da própria Caixa segurando a lei enquanto isso.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/782. PROVA VERMELHO->VERDE medida na bancada, no guarda novo (services/sugestoes/tests/test_a_caixa_explica_as_etapas.py): com os templates no estado anterior, 9 failed / 3 passed; com as telas prontas, 13 passed. Suite da celula 522 -> 535 passed. black --check limpo em 106 arquivos. Freeze de contrato PASS (947 linhas identicas, 9 operacoes com autenticacao conferida na fonte). Muralhas do repositorio 13/13 PASS, travessao incluido. O HTML gerado foi lido com os olhos: a frase da situacao no topo da pagina da ideia e as quatro etapas dentro do bloco que abre. A afirmacao \"votar nunca fecha\" foi conferida no proprio codigo que vota (apps/core/participacao.py::votar), que so recusa sugestao arquivada e nunca le o status, e no template do quadro, que desenha o botao em todo card sem condicao de etapa. O buraco do portao do travessao foi medido lendo ci/travessao.py::superficie, que varre templates/, traducoes/, documentos/ e management/commands/, e nao models.py.",
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
