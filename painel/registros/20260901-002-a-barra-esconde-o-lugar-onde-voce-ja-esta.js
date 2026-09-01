(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-002-a-barra-esconde-o-lugar-onde-voce-ja-esta",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A barra esconde o lugar onde voce ja esta, e ganhou a Caixa e as Conquistas",
  detalhe: "Seu pedido: \"no inicio em / ele mostra Forum, Caixa, e deixa pronto pra mostrar Perfil e Conquistas (em breve). E no Forum ele, obviamente, nao mostra o menu Forum, e a mesma coisa em Caixa\".\n\nA REGRA NOVA: o item que leva para onde voce ja esta nao aparece. Na pagina inicial some o Inicio; no forum some o Forum; na Caixa some a Caixa. Um link para o lugar onde a pessoa ja esta gasta espaco e ensina o aluno a desconfiar do menu.\n\nA regra vale por AREA, e nao por pagina: dentro de uma conversa do forum o item Forum continua sumindo, porque voce continua no forum.\n\nDOIS ITENS NOVOS entraram: Caixa e Conquistas. Os dois nascem visiveis so para quem ja entrou, porque sao areas de aluno e mandar um visitante para uma tela de login sem contexto e atrito, nao convite. Voce muda isso num clique em /admin/menu/.\n\nPERFIL NAO ENTROU, e a ausencia foi pensada: eu medi antes de escrever. O endereco /conquistas/ responde 200, e o /perfil responde 404 (a pagina ainda nao existe). Um item de menu para uma pagina que nao existe e um link quebrado no topo de TODAS as paginas do site, o que e pior que a falta dele. No dia em que a pagina nascer, o item entra pela tela, sem robo nenhum.\n\nA MARCA DE 'VOCE ESTA AQUI' SAIU JUNTO, e nao por descuido: com a regra nova nenhum item pode ser a pagina atual, entao o destaque virou impossivel. Deixar o codigo dele seria deixar uma intencao morta para a proxima pessoa ler como se fosse viva.\n\nUM ACHADO DE CAMINHO, que valeu a pena: os testes do forum e da Caixa mediam esses enderecos como se eles fossem a raiz do site, e nao /forum/ e /forms/sugestoes/ como sao de verdade. Com a regra nova isso deixou de ser inofensivo, porque e exatamente o endereco que a regra compara. Os testes passaram a medir com o endereco real, e so entao eles provam o mundo que existe.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/810",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
