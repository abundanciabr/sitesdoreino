(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-024-quadrinho-de-progresso-na-home",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A home passou a mostrar, para quem entrou, o degrau dele na trilha da escola",
  detalhe: "A primeira tela depois do login e a raiz do site. Ate hoje o progresso do aluno so aparecia para quem abrisse a pagina de conquistas de proposito, e quem entrava via so o aviso de novidade.\n\nAgora, logo abaixo desse aviso, quem entrou ve um quadrinho discreto: o numero do degrau em destaque, uma barrinha de progresso, e em letra pequena o quanto falta para o proximo. O total de pontos nao aparece na tela de proposito, e o nome do degrau (Aprendiz, Modelador) tambem nao: esse nome mora na parte das conquistas, e inventar um aqui faria as duas telas chamarem a mesma coisa por nomes diferentes.\n\nO QUE VOCE VAI VER HOJE, e nao e defeito: nada. O quadrinho so aparece para quem ja tem ponto, e ninguem tem ainda, porque a economia da escola continua inteira desligada. Ele nasce sozinho, pessoa por pessoa, no dia em que voce ligar a primeira regra na tela /admin/economia/.\n\nE HA UM PASSO SEU, de uma linha, para a home poder perguntar os pontos a parte das conquistas: o script infra/provisionar-par-do-funil-com-a-gamificacao.sh, rodado dentro da VPS. Se ninguem rodar, a home abre exatamente como abre hoje, sem o quadrinho, e nada quebra. O site continua igual em tudo.\n\nA home tambem nao cai se a parte das conquistas ficar fora do ar: o quadrinho simplesmente some, a pagina abre normal, e nenhuma barra em zero finge que a pessoa tem progresso.\n\nProva: a suite de testes do site foi de 466 para 506 testes, toda verde, e cinco defeitos foram introduzidos de proposito no codigo para conferir que os testes novos realmente pegam cada um deles. O quinto nao foi pego na primeira tentativa, e o conserto do proprio teste virou a licao 266 do catalogo.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/829",
  verificado_em: "2026-09-01",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
