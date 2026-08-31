(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-031-o-site-agora-se-instala-como-app-no-celular",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O site agora se instala como app no celular, e ele mesmo convida",
  detalhe: "Voce pediu hoje: o site precisa poder ser instalado nos aparelhos que nao sao PC, para que os avisos cheguem a quem estuda aqui. Esta feito no site da escola (meshcraft.top), nos tres idiomas.\n\nCOMO FICA PARA QUEM ABRE O SITE NO CELULAR: aparece um cartaz verde no fim da pagina dizendo 'Instale o Meshcraft no seu celular'. No Android, um toque no botao abre a caixa de instalacao do proprio sistema. No iPhone nao existe essa caixa (a Apple nao deixa o site abri-la), entao o cartaz ensina o caminho de tres passos pelo botao Compartilhar. Instalado, o site vira um icone na tela de inicio, com desenho e cor proprios, e abre em tela cheia, sem a barra do navegador.\n\nO CARTAZ TEM EDUCACAO: nao aparece em computador, nao aparece para quem ja instalou, e some por 30 dias se a pessoa clicar em 'Agora nao'. E quem instalou em portugues abre o app em portugues, nao em ingles.\n\nO app tambem abre sem internet, mostrando a ultima versao que ele guardou. Mas ele pergunta a rede PRIMEIRO, sempre: e a regra que impede o app instalado de mostrar uma pagina velha enquanto o site esta atualizado. Esse engano e silencioso (a medicao de fora continua certa e so o celular de quem instalou mostra a pagina de ontem), entao virou armadilha 241 e tem teste que reprova se alguem inverter a ordem.\n\nOS SITES ANTIGOS (as vitrines em outros dominios) nao mudaram um byte. O app e do site da escola, que tem gente entrando e aviso para mandar.\n\nO QUE ISTO AINDA NAO FAZ, e e o proximo degrau: mandar a notificacao em si. Instalar e o pre-requisito no iPhone, e era a metade que faltava; o aviso empurrado precisa de uma chave nova no servidor e de trabalho na celula de notificacoes. Levei a escolha a voce em separado, para nao decidir sozinho o que voce quer que o celular dos alunos receba.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/706. 382 testes verdes na celula funil (26 deles novos, so deste assunto), black limpo, 13 muralhas PASS. PROVA VERMELHO->VERDE: quebrando de proposito as tres pecas (o cartaz fora da pagina, a ordem rede/cache invertida no sw.js, um icone apagado), a suite reprova em 6 testes nomeados, entre eles 'test_o_service_worker_pede_a_rede_antes_do_cache' e 'test_o_cartaz_nasce_escondido_e_com_os_dois_caminhos'; desfeita a quebra, verde. O guarda do mapa do site e o test_d6_roteamento cobraram as duas rotas novas na hora em que elas nasceram.",
  verificado_em: "2026-08-31",
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
