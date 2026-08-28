(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-060-o-forum-da-escola-nasceu",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O fórum da escola nasceu — a fundação está de pé, e ela já vem com botão de desfazer",
  detalhe: "Você autorizou, e a parte nova do site nasceu. É a quinta vez que isso acontece no projeto (depois da Caixa de Sugestões, do login, do sininho e da área administrativa).\n\nO QUE ISSO É, EM LINGUAGEM SIMPLES: ainda não tem tela nenhuma para ver. O que nasceu foi a fundação — o esqueleto da casa, a fiação e os alarmes. É de propósito, e é a ordem que o veredito mandou seguir: fundação antes de parede.\n\nO QUE JÁ ESTÁ GARANTIDO POR MECANISMO, e não por promessa:\n\n1. O FÓRUM NÃO VAI PODER DESLOGAR VOCÊ DO SITE. Existe um alarme que confere isso sozinho, e eu o testei sabotando o código de propósito: quando plantei o erro, o alarme ficou vermelho na hora. É a proteção mais importante desta parte, porque foi justamente a sua exigência de um login só que decidiu construir em vez de instalar.\n\n2. O ENDEREÇO NÃO ESTÁ CRAVADO NO CÓDIGO. O fórum vai morar em meshcraft.top/forum, mas o código não sabe disso — quem sabe é a configuração. Também testei sabotando: cravar o endereço deixa três alarmes vermelhos.\n\n3. ELE JÁ NASCEU COM BOTÃO DE DESFAZER. Se um dia uma mudança no fórum der errado, dá para voltar atrás com um comando. Já aconteceu de uma parte do site nascer sem isso e a gente descobrir tarde.\n\nUMA COISA VAI FICAR VERMELHA, E É ESPERADO: a publicação automática desta parte nova falha até o passo em que o servidor souber que ela existe. Está previsto, é assim em toda parte nova, e não é defeito. Nada do site sai do ar por causa disso.\n\nUM ATRITO QUE APARECEU E VALE VOCÊ SABER: dois controles de qualidade do projeto se contradiziam quando uma parte nova nasce — um exigia atualizar o mapa técnico junto, o outro proibia mexer em duas partes no mesmo pedido. Não dava para os dois ficarem verdes ao mesmo tempo. Resolvi pela ORDEM, sem afrouxar nenhum dos dois: o mapa foi num pedido antes, a célula no seguinte. Fica anotado porque a próxima parte nova vai esbarrar na mesma coisa.\n\nO QUE VEM A SEGUIR: o modelo de dados — áreas, tópicos, mensagens e a marca de 'li até aqui'. É a peça que decide se um dia dá para trocar o fórum inteiro sem refazer a escola.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/407 (a celula) e https://github.com/abundanciabr/sitesdoreino/pull/408 (o mapa para IA, que precisou vir antes). Ambos MERGED em 28/08/2026, conferidos por gh pr view. Suite da celula: 7 verdes. Lint black: 10 arquivos limpos. PROVA POR SABOTAGEM, duas mutacoes: (1) instalar SessionMiddleware => test_sem_middleware_de_sessao FALHOU; (2) cravar 'forum/healthz' no urlconf => os 3 casos de test_healthz_script_name.py FALHARAM. Restaurado, 7 verdes. Portao de contrato: freeze-de-contrato.sh forum => SKIP declarado. rollback.yml de 12 para 13 celulas, batendo com services/. Guarda dos guardas: 28 declarados em 20 invariantes, divida INALTERADA em 37. Numero deste registro alocado pelo servidor via ci/reservar.py.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: "20260828-055-o-veredito-do-forum-construir-na-casa",
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: true,
  impacto: null
});})();
