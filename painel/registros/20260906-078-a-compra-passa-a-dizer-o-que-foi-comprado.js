(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-078-a-compra-passa-a-dizer-o-que-foi-comprado",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "Degrau 2: a tela de compra passa a guardar o que a pessoa comprou",
  detalhe: "Segundo dos quatro degraus para fechar o buraco que voce mandou fechar. Quando alguem inicia uma compra, o pedido passa a guardar QUAL produto e.\n\nEU NAO ENCOSTEI no Mercado Pago nem na tela que o cliente ve, como combinamos. O produto viaja num espaco que ja existia e que o sistema de pagamento ja usa para outra coisa parecida, entao nem foi preciso mexer em mais um contrato.\n\nQUANDO A PESSOA COMPRA UM EXTRA junto (aqueles adicionais na hora de pagar), o produto guardado e o PRINCIPAL: um pedido gera uma matricula, e o extra nao vira curso proprio.\n\nUM SUSTO NO CAMINHO: ao salvar, varri 6010 arquivos de biblioteca para dentro por engano, porque o projeto nao tinha regra ignorando a pasta de ambiente do Python. Desfiz e a regra entrou junto, para nao acontecer com ninguem.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1219 (PR #1219). Suite da celula checkout em PostgreSQL real: 62 passed, com a main do rito #1209 dentro. Prova por mutacao, cada vermelho na assercao: tirar o produto do metadata (3 failed) e mandar o bump em vez do item principal (assert 'prod-bump-a' == 'prod-site-aaa'). Sabotagem por script, com ast.parse antes de cada rodada e restauracao num finally (armadilhas/369). black --check: 31 arquivos, nenhum a reformatar.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
