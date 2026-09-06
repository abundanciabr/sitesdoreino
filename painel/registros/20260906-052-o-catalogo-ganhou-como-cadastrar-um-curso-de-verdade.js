(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-052-o-catalogo-ganhou-como-cadastrar-um-curso-de-verdade",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O catalogo ganhou como cadastrar um curso de verdade",
  detalhe: "Um robo achou um furo que eu nao tinha visto, e ele era fundo: NAO EXISTIA caminho nenhum para um curso de verdade nascer no catalogo. O unico produto que o sistema sabia criar era o Curso Esqueleto, que e peca de teste.\n\nO QUE ISSO SIGNIFICAVA: mesmo com a lista pronta, a tela de liberar aluno ofereceria hoje um curso FALSO, e a pessoa abriria a sala matriculada nele. E o mesmo erro que a lei quis impedir, entrando por outra porta.\n\nAgora existe o comando, ele imprime o numero de identificacao do curso (que e o que voce vai colar para apontar as matriculas antigas), e rodar duas vezes nao duplica nada. Rodar de novo com outro nome AVISA e nao renomeia calado: o nome e o que a pessoa le na hora de escolher.\n\nO PRECO NASCE EM ZERO de proposito: quem cobra e a oferta do site, e a plataforma ainda nao vende. Zero aqui quer dizer 'nao esta a venda por este produto', nao 'de graca'.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1194 (PR #1194). Suite da celula catalogo em PostgreSQL real: 83 passed. Prova por mutacao com 4 sabotagens, cada vermelho caindo na assercao: apelido sem minusculas (assert 0 == 1), preco fora do zero (assert 9900 == 0), aviso de renomeacao removido, recusa de apelido vazio removida. black --check: 34 arquivos, nenhum a reformatar. Freeze com a main do #1190 dentro: contrato/catalogo PASS identico ao congelado (587 linhas). Leva junto a TAR-227.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
