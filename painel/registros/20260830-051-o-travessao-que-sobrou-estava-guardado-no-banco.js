(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-051-o-travessao-que-sobrou-estava-guardado-no-banco",
  tipo: "incidente",
  quando: "2026-08-30",
  titulo: "Voce achou um travessao que eu tinha dado como resolvido: ele estava guardado no banco, nao no texto",
  detalhe: "Voce abriu o forum e viu um travessao na area \"Mostre seu trabalho\", depois de eu ter reportado o site inteiro limpo. Voce estava certo e eu estava errado.\n\nO QUE ACONTECEU, sem tecniques: existe um arquivo que CRIA as areas do forum, e eu corrigi o texto nele. So que esse arquivo age uma vez so, quando a area nasce. As quatro areas nasceram na quinta-feira, e o texto que voce le esta guardado no banco de dados desde entao. Corrigir a receita nao muda o bolo que ja foi assado.\n\nPior: o teste automatico concordava comigo. Ele roda sempre num banco vazio, onde a area nem existe -- entao a diferenca entre a receita e o bolo nunca aparecia.\n\nO QUE CONSERTEI: duas instrucoes de banco que rodam sozinhas quando a entrega sobe. Uma troca a descricao da area do forum; a outra troca um comentario de demonstracao na Caixa de Sugestoes, que tinha o mesmo problema (ele foi semeado ontem a noite, entao tambem ja estava gravado). As duas so agem se o texto for exatamente o antigo: se alguem tiver reescrito aquilo, elas nao encostam.\n\nO QUE ISSO ENSINA, e vale mais que o conserto: o porteiro que criei vigia ARQUIVOS. Texto que ja esta guardado no banco ele nao ve, e nunca vera. Varri todo o resto do que os semeadores criam (categorias da Caixa, quadro, produtos do catalogo, as outras tres areas do forum) e nao ha mais nenhum. Mas essa e uma fronteira real do porteiro, e agora ela esta escrita.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/599",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
