(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-129-o-portao-do-travessao-enxerga-o-codigo",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O guarda que caça travessão passou a olhar também dentro do código, e achou seis publicados",
  detalhe: "Você autorizou isto na conversa das etapas da Caixa, quando eu contei que o guarda tinha um ponto cego.\n\nO problema, em uma frase: o guarda que confere travessão só olhava os arquivos de tela, e uma parte do que o aluno lê não mora lá. Os nomes das etapas (\"Em análise\" e os outros cinco) sempre viveram num arquivo de código, fora do alcance dele. Nunca deu problema até hoje, mas isso era sorte, não regra.\n\nAgora o guarda olha duas coisas novas. A primeira é automática e não depende de ninguém lembrar: qualquer lista de situações que apareça na tela entra sozinha, e ele confere só o nome que a pessoa lê, nunca o código interno. A segunda é para arquivos que escrevem frases inteiras para o aluno, e esses precisam se declarar com uma marca.\n\nNa primeira vez que rodou, ele achou SEIS travessões publicados que ninguém tinha visto: três nos nomes das áreas do fórum e três na Caixa. Duas destas últimas são frases que o aluno lê quando erra: a que pede para contar o problema ao criar uma sugestão, e o aviso de que ele já publicou três ideias na semana. Todas as seis foram reescritas em português correto, não só com o traço apagado.\n\nO que deixei de propósito de fora, e é a parte mais importante da decisão: NÃO mandei o guarda olhar todo o código. Medi antes de escolher. Olhar tudo daria 294 achados, quase todos em mensagens que só um programador lê, e várias delas dentro do próprio painel que LISTA os travessões (onde o traço é o assunto, não um erro). Um guarda que grita 294 vezes por nada é um guarda que as pessoas aprendem a ignorar. A regra estreita achou 3 em 80, e os 3 eram de verdade.\n\nEste trabalho mexeu na pasta dos guardas e no arquivo de leis da raiz, os dois protegidos e que exigem sua autorização. Foi feito com o seu mandato explícito, e está anunciado aqui pelo nome.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/803, mandato do mantenedor por pergunta estruturada em 31/08/2026 (TAR-087). PROVA VERMELHO->VERDE: os 10 guardas novos de ci/tests/test_travessao.py secao 9 dao 4 failed contra o portao antigo (git stash do ci/travessao.py) e 55 passed com o novo. MEDICAO que decidiu o desenho, feita antes de escrever a regra: varrer todo .py de celula daria 294 travessoes em 61 arquivos; varrer toda constante MAIUSCULA de modulo daria 94 em 2758 strings; a regra dos rotulos de Choices varre 80 strings e achou 3. Suite do repositorio 1406 passed. ci/travessao.py PASS com 81 arquivos inspecionados (eram 75) e divida herdada intacta em 3. Muralhas 13/13 PASS, cerca-de-celula OK com as 2 celulas tocadas (forum, sugestoes). Celula forum 207 passed; celula sugestoes 574 passed com freeze de contrato PASS. black limpo em ci/, forum (53 arquivos) e sugestoes (111 arquivos).",
  verificado_em: "2026-08-31",
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
