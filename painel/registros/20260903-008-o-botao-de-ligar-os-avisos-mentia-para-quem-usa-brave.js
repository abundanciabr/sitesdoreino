(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-008-o-botao-de-ligar-os-avisos-mentia-para-quem-usa-brave",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "O botão de ligar os avisos mandava esperar por algo que nunca ia chegar",
  detalhe: "Você clicou em 'Ligar os avisos' e a tela respondeu 'Não deu certo agora. Você pode tentar de novo mais tarde.'. Eu fui atrás, e o site estava certo o tempo todo: quem recusou foi o seu navegador.\n\nO QUE ERA: você usa o Brave, e ele vem de fábrica com os avisos do Google desligados, por privacidade. Com essa chave desligada, nenhum site consegue mandar aviso para a sua tela. O pedido nem chegou ao nosso servidor, e é por isso que não havia erro nenhum do nosso lado para eu encontrar. Antes de chegar nisso eu descartei, medindo: a chave do aviso no servidor, o endereço do botão, o idioma da página, a permissão do navegador, firewall e antivírus.\n\nO QUE ESTAVA ERRADO NO SITE, E ISSO SIM ERA GRAVE: a tela dizia a MESMA frase nos dois casos, quando quem recusou era o navegador e quando era o nosso servidor. Quando é o navegador, 'tente de novo mais tarde' é mentira: tentar amanhã dá exatamente no mesmo, porque nada muda sozinho. Um aluno seu que use Brave clicaria, voltaria semana que vem, clicaria de novo e desistiria achando que o site é quebrado. E ninguém aqui ficaria sabendo, porque esse tipo de falha não deixa rastro em servidor nenhum. Você só descobriu porque eu pude ler o erro dentro do seu navegador.\n\nO QUE MUDOU: agora são duas frases. Quando o nosso lado falha, continua 'tente de novo mais tarde', que ali é conselho honesto. Quando é o navegador, a tela passa a dizer o que fazer: olhar os ajustes de privacidade dele. Nos três idiomas. A frase não cita o Brave pelo nome de propósito, porque a lista de navegadores que fazem isso muda sozinha com o tempo e um texto que nomeia um deles envelhece no dia seguinte.\n\nO QUE FALTA VOCÊ FAZER, e é rápido: abra brave://settings/privacy, ligue 'Usar serviços do Google para mensagens push', feche e reabra o Brave inteiro, e clique em 'Ligar os avisos' outra vez. Aí eu registro que funcionou.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/905. Causa medida no navegador do mantenedor: AbortError Registration failed - push service error, com a chave VAPID (87 caracteres), a rota /avisos/ligar (401 sem sessão), o prefixo de idioma, a permissão concedida, as 4 portas do Google abertas e o service worker pronto todos descartados antes. Suíte da célula funil 562 verde, black limpo, 13 muralhas em PASS (a do travessão inspecionou o texto novo dos 3 idiomas). Duas mutações e dois vermelhos: o .catch genérico de volta mata o teste estrutural, e a frase do navegador voltando a mandar esperar mata os dois testes de texto entregue. Armadilha 297 acrescentada.",
  verificado_em: "2026-09-03",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: "Você continua sem receber aviso nenhum no computador. O site funciona igual para todo mundo, e a correção da frase já vale para os alunos: só o seu Brave fica mudo.",
  recomendacao: "Ligar a chavinha em brave://settings/privacy, fechar e reabrir o Brave, e clicar em 'Ligar os avisos' de novo. Se preferir não mexer no Brave, abrir o site no Edge também resolve.",
  reversivel: true,
  impacto: "baixo"
});})();
