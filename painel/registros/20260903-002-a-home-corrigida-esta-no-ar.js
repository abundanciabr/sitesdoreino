(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-002-a-home-corrigida-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-03",
  titulo: "A home sem o botão errado está no ar, e o deploy engasgou uma vez antes",
  detalhe: "O PR #897 está em produção. Abra meshcraft.top com a sua conta e o convite \"Pedir entrada\" não deve mais aparecer: no lugar dele fica o caminho da Caixa, que é o que você de fato tem.\n\nO DEPLOY PRECISOU DE DUAS TENTATIVAS, e a primeira falhou por rede, não por defeito. A imagem foi construída inteira e recebeu o nome certo; o que quebrou foi o ENVIO dela para o depósito de imagens, com a mensagem \"unknown blob\" no meio do upload. Repeti sem merge novo e a segunda passou em 2min38s. Nenhuma linha de código mudou entre as duas.\n\nPOR QUE ISSO ESTÁ ESCRITO AQUI EM VEZ DE VIRAR ARMADILHA: é a primeira vez que esse engasgo aparece no projeto, procurei e não há precedente. Uma ocorrência só não distingue \"a rede tossiu\" de \"tem algo errado com o nosso envio\". Se acontecer de novo, aí vira armadilha com a receita pronta.\n\nO QUE EU CONFERI DE FORA, e o que NÃO consegui: a página inicial responde, a página de cadastro responde, o fórum responde, e a Caixa manda para o login como deve. O que eu não tenho como medir daqui é a SUA tela: para ver o ramo da equipe é preciso estar dentro da sua sessão, e eu não entro na sua conta. Essa metade é sua, e é um recarregar de página.\n\nSE O BOTÃO AINDA APARECER depois de recarregar, me avise: aí a causa é outra e eu volto a investigar, porque a que eu corrigi está medida e provada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33698404188",
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
