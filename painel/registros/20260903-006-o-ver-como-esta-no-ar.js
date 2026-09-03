(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-006-o-ver-como-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O \"Ver como\" está no ar, e agora falta você experimentar",
  detalhe: "O PR #902 está em produção, deploy verde em 3min56s. Entre no site e procure \"Ver como\" no canto de cima, ao lado do Sair.\n\nO QUE EU MEDI DE FORA: a página inicial responde, a página de cadastro responde, o fórum responde. A entrega subiu e o site está de pé.\n\nO QUE EU **NÃO** CONSEGUI PROVAR DAQUI, e prefiro dizer em vez de deixar você achar que está tudo conferido: a tela do \"Ver como\" responde \"não encontrada\" para mim, e isso é exatamente o que ela deve fazer com quem não é da equipe. Só que, de fora, esse \"não encontrada\" é indistinguível de \"a página não subiu\". As duas coisas parecem iguais para quem não tem a sua sessão, e eu não entro na sua conta. Quem separa uma da outra é você, abrindo o site logado: se o atalho aparecer, subiu.\n\nEssa ambiguidade não é falha do trabalho, é consequência do desenho: uma porta fail-closed não conta para estranhos que existe. Vale a pena saber que é assim, porque ela vai se repetir em toda tela que só a equipe vê.\n\nO QUE ESTÁ PROVADO POR TESTE, e não por medição de fora: são 22 testes novos, 559 na célula do site. Eles cobrem quem pode se disfarçar, quem não pode, as quatro situações, a tarja, e o fato de a prévia não mexer na sua sessão.\n\nUM DETALHE QUE VOCÊ VAI NOTAR: durante a prévia, o botão \"Admin\" some do menu do topo. É de propósito. Um aluno de verdade nunca vê aquele botão, e se ele continuasse aparecendo a prévia estaria mentindo justamente sobre o que ela existe para mostrar. Ele volta sozinho quando você clicar em \"Voltar ao normal\".",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33702311465",
  verificado_em: "2026-09-03",
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
