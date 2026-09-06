(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-049-o-catalogo-aprendeu-a-listar-os-produtos",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "O catalogo aprendeu a listar os produtos, e a tela de liberar tem de onde ler",
  detalhe: "Degrau 2 da escada do contrato de hoje. O catalogo sabia buscar UM produto pelo numero dele e nao sabia listar nenhum, entao a tela de liberar nao tinha de onde tirar a lista de cursos que voce pediu. Agora sabe.\n\nSO OS ATIVOS, de proposito: a lista existe para escolher em qual curso liberar alguem, e ninguem deve ser liberado num curso aposentado. Quem ja esta matriculado num curso aposentado continua vendo o nome dele normalmente.\n\nUM TESTE MEU QUE PASSOU POR ACASO, e o conserto: a prova por sabotagem pegou um teste fraco antes de ele entrar. Eu conferia a ordem alfabetica da lista, mas os numeros de identificacao dos produtos sao sorteados, e uma em cada seis rodadas a ordem sairia alfabetica por sorte. O teste teria entrado verde sem provar nada. Escolhi os numeros a mao para que qualquer ordem errada reprove sempre.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1190 (PR #1190). Suite da celula catalogo em PostgreSQL real: 81 passed (linha de base antes de tocar em nada: 76). Prova por mutacao: tirar o filtro de ativos da vermelho na assercao (assert com Curso Aposentado na lista); trocar a ordem do nome pela do id da vermelho na assercao depois do conserto. black --check: 33 arquivos, nenhum a reformatar. Freeze com a main do rito dentro: contrato/catalogo PASS identico ao congelado (587 linhas), seguranca/catalogo PASS 6 operacoes.",
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
