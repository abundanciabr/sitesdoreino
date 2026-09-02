(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-050-a-area-de-admin-ganhou-menu-e-rodape-proprios",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "A área de administração ganhou um menu e um rodapé só dela",
  detalhe: "Você pediu: uma forma de todas as páginas de /admin terem menu e rodapé próprios, que não são os do site. Está pronto.\n\nO que mudou na prática: agora toda tela da administração abre com uma faixa de botões no topo, e o botão do lugar onde você está fica aceso. São nove: Visão geral, Escola, Caixa, Pontos, Documentos, Menu do site, Lançamento, Mapa do site e Painel do sistema. Dá para pular de qualquer tela para qualquer outra num clique.\n\nAntes não dava. Cada tela tinha uma faixa escrita à mão que só mostrava o nome do lugar e não levava a canto nenhum: para sair dos Pontos e chegar na Caixa, você tinha de voltar pela visão geral. Essa faixa estava copiada em 21 telas, uma cópia por tela, e no dia em que um robô esquecesse de copiá-la a tela nova nasceria sem ela e ninguém notaria.\n\nNo pé de toda tela nasceu também um rodapé desta área, que não é o do site: ele diz que você está na sala de máquinas e abre as duas saídas, o site como um visitante o vê e a biblioteca pública.\n\nDuas coisas que vale você saber:\n\nEste menu NÃO é o menu do site que você configura em /admin/menu/. Aquele é o topo que os alunos veem, e você manda nele. Este é a navegação do bastidor, e ele muda sozinho quando uma tela nova nasce, porque é o mapa do site quem manda nele. Se um robô criar uma seção nova e esquecer de pô-la no menu, a esteira recusa o trabalho dele até ele pôr.\n\nQuem não é administrador continua sem ver nada disso. Quem não está na sua lista recebe \"esta página não existe\", e essa tela usa o mesmo molde das outras: se o menu aparecesse ali, um estranho leria o mapa inteiro da sua área de administração. Tem teste travando isso.\n\nUma exceção, dita na cara: o painel do sistema (/admin/painel/) é a única página que não tem a faixa nova, porque ele não é montado como as outras, é um arquivo pronto. Ele não ficou sem saída: ganhou um link \"Administração\" no canto das abas dele, que faltava desde sempre.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/886",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
