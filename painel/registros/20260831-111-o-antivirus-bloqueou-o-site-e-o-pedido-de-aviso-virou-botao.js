(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-111-o-antivirus-bloqueou-o-site-e-o-pedido-de-aviso-virou-botao",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "O antivírus bloqueou o site por causa do pedido de aviso; agora ele só abre com um toque",
  detalhe: "O QUE VOCÊ VIU: a tela do Malwarebytes dizendo 'Site bloqueado devido a excesso de solicitação de notificações', no dia da inauguração. Você mandou o print, marcado urgente, e estava certo em tratar como urgente.\n\nA CAUSA: era o pedido de aviso no celular que entrou hoje mais cedo (registro 20260831-075). Ele abria a caixa de permissão SOZINHO, ao carregar a página, e pedia de novo a cada página visitada. Para um antivírus, pedir permissão de notificação sem a pessoa ter tocado em nada, várias vezes, é o retrato falado dos sites de golpe que sequestram as notificações para mandar propaganda. O Malwarebytes viu esse padrão e bloqueou o site inteiro para proteger o visitante.\n\nO CONSERTO, que entra no ar com o deploy deste PR (confirmo em registro próprio depois do pouso): a caixa do navegador só abre depois de um TOQUE no botão 'Ligar os avisos' do cartaz, em todo aparelho por igual. Isso desfaz metade do que você pediu de manhã ('sem botão na página'), e eu preciso ser franco sobre o porquê: o caminho sem botão é tecnicamente idêntico ao comportamento que os antivírus caçam. Não existe versão dele que não arrisque o bloqueio do site na frente dos alunos. O botão é o único desenho seguro, e é também o que iPhone e Firefox já exigiam.\n\nO QUE ISSO MUDA PARA O ALUNO: em vez da caixa do celular aparecer sozinha depois de entrar, ele vê um convite educado do site com o botão. Tocou, a caixa oficial abre, e o resto segue igual.\n\nSE O SEU MALWAREBYTES AINDA MOSTRAR O BLOQUEIO depois do conserto entrar no ar: é memória local do programa. Abrir o site e clicar em 'Continuar nesse site' uma vez resolve; visitantes novos não devem mais ver bloqueio nenhum.",
  autoridade: "sessao",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/786. 448 testes verdes na célula funil, com guarda novo que reprova qualquer volta do pedido automático (test_nenhum_pedido_de_permissao_abre_sem_um_toque). Padrão documentado em armadilhas/257.",
  verificado_em: "2026-08-31",
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
