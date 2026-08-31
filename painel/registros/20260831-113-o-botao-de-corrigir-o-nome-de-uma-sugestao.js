(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-113-o-botao-de-corrigir-o-nome-de-uma-sugestao",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Terceiro degrau, e o que voce pediu: o botao de corrigir o nome e o texto de uma sugestao ja existe",
  detalhe: "Este e o degrau que voce vai usar. Depois que ele subir para o site, abra a Caixa de Sugestoes na area de administracao, clique na ideia do 'turorial' e voce vai achar, logo abaixo do texto do aluno, uma parte nova chamada CORRIGIR O TEXTO.\n\nCOMO E: os campos ja vem preenchidos com o que esta escrito agora — o nome, o texto do problema e a solucao que ele propos. Voce conserta a letra errada direto ali e clica em salvar. Nao e um formulario em branco, e o texto de verdade esperando o seu conserto.\n\nUMA LINHA DA TELA MERECE ATENCAO, e ela esta la de proposito: a propria pagina avisa que o aluno vai ver o texto novo SEM MARCA NENHUMA. Voce precisa saber disso antes de clicar, porque e a diferenca entre consertar uma digitacao e reescrever a fala de alguem em silencio. Foi a sua escolha, e eu concordo com ela para erro de digitacao — mas quem clica merece ver a consequencia escrita.\n\nEMBAIXO DO FORMULARIO fica o rastro: o que ja foi corrigido nesta ideia, com o texto que estava escrito ANTES, quem corrigiu e a data. So voce e quem administra enxerga isso; o aluno nunca. E ele nao pode ser apagado nem editado por ninguem.\n\nOS DOIS CASOS EM QUE A TELA DIZ NAO, para nao te pegar de surpresa: se voce clicar em salvar sem ter mudado nada, ela recusa dizendo isso (em vez de responder 'pronto' sem ter feito nada); e ideia que voce ja apagou de vez nao mostra o formulario, porque corrigir o texto dela seria trazer de volta o que o apagar prometeu destruir.\n\nUMA COISA QUE EU ACHEI ENQUANTO FAZIA, e que voce deve saber sem se preocupar: ao proteger a trava da auditoria numa mudanca do banco de dados, fui conferir se o robo de testes teria me cobrado caso eu esquecesse — e nao teria. Medi isso de verdade, removendo a protecao de proposito e vendo o teste ficar verde. Uma mudanca de outro robo, que entrou hoje mesmo, passou sem essa protecao pelo mesmo motivo. NAO AFETA O SITE NO AR (la o banco e outro, e a trava sobrevive); afeta so a maquina de quem programa. Ficou anotado no caderno de armadilhas, com a medicao junto, e a minha mudanca ja repoe a trava para as duas.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/788 (consumidor de https://github.com/abundanciabr/sitesdoreino/pull/779 e https://github.com/abundanciabr/sitesdoreino/pull/785). PROVA VERMELHO->VERDE, sem rede: contra o codigo de origin/main o tests/test_caixa_acoes.py da 10 failed / 46 passed (as 8 do gesto novo mais as duas varreduras de rota que passaram a incluir caixa_corrigir); com o PR, 560 passed na celula (eram 544). Entre os guardas: a tela aguenta o rastro AUSENTE (o campo e opcional no contrato), a ideia apagada nao oferece o formulario, a recusa da Caixa chega inteira ao operador e a tentativa RECUSADA deixa linha na auditoria. ci/ci.py --apenas muralhas PASS nas 13, com painel/mapa-do-site.json declarando o endereco novo. black --check limpo em 82 arquivos. A armadilha 256 (o guarda cego no CI) foi MEDIDA: com o RunPython removido de proposito e DATABASE_URL em Postgres, o teste-detector da 246 da '1 passed'.",
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
