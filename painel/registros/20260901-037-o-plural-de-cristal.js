(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-037-o-plural-de-cristal",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A tela da economia dizia Cristalis, e agora diz Cristais",
  detalhe: "Voce achou isto na sua propria tela, ao ligar a medalha das dez forjas: o cartao dizia 'Vale 80 pontos e 10 Cristalis'. O plural de Cristal e Cristais.\n\nA causa era uma peca do Django que ACRESCENTA a terminacao em vez de trocar. Ela funciona para palavra que so ganha um s no fim (uma ideia, duas ideias), e nao serve para palavra cuja raiz muda. Corrigido nos dois lugares onde aparecia, que sao os unicos: varri o repositorio inteiro e todo o resto usa a forma certa.\n\nDOIS testes guardam isso agora, e um so nao pegaria o defeito: o singular estava certo antes e depois, entao um teste que olhasse so ele passaria com o erro no lugar. Provei cada um quebrando o codigo de proposito e vendo o teste certo ficar vermelho, e conferi que nenhum dos dois pega a falha do outro.\n\nSuite da area administrativa: 578 para 580 verdes.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/841",
  verificado_em: "2026-09-01",
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
