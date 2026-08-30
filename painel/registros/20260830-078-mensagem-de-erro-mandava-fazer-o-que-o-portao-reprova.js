(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-078-mensagem-de-erro-mandava-fazer-o-que-o-portao-reprova",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "Uma mensagem de erro mandava os robos fazerem exatamente o que outro guarda recusa — tres cairam nela no mesmo dia",
  detalhe: "Quando dois robos escolhiam por acaso o mesmo numero para uma licao nova, o programa que organiza o catalogo parava e dizia: \"escolha voce mesmo o proximo numero livre\". Quem obedecia era barrado pelo guarda seguinte, na mesma conferencia, com a frase \"numero escolhido a mao\".\n\nOs dois avisos vinham do mesmo sistema e diziam coisas opostas. Em 30/08/2026 isso custou uma rodada de conferencia a TRES robos diferentes, que nao se conheciam. Nenhum deles errou: a instrucao estava velha. A regra da casa mudou em 29/08 — numero se PEDE ao almoxarife, que entrega um so para cada um — e essa mensagem nunca foi atualizada junto.\n\nAgora ela manda pedir o numero, e nao escolhe nenhum. A mesma receita velha estava escrita em outros tres lugares (o cabecalho do indice do catalogo, a mensagem de um teste, e o paragrafo de instrucao da licao 085); todos cairam no mesmo PR.\n\nUm teste novo passou a vigiar isso em toda conferencia: ele forca a colisao e exige que a mensagem ensine o caminho certo e nao nomeie numero nenhum. Sem o conserto ele fica vermelho.\n\nA licao maior ficou escrita como armadilhas/227: quando uma regra ganha um guarda automatico, tudo que ENSINA a regra antiga precisa ser corrigido junto — mensagens de erro sao lidas por quem esta com pressa e errado, no momento de maior obediencia que existe.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/640 — TAR-036; vermelho na assercao (assert 'ci/reservar.py numero armadilha' in erro, 1 failed) e verde depois: 33 passed nos testes do indice e das reservas, testador 1309 passed, muralhas RESULTADO PASS",
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
