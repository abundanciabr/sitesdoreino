(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-018-quando-a-linha-principal-quebra-a-cura-ja-vem-pronta",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "Quando a linha principal do projeto quebra, a cura já chega escrita",
  detalhe: "Existe um alarme que dispara quando alguma coisa entra e quebra o projeto: ele abre um aviso. Só que aviso não conserta nada — alguém precisava ler, entender e desfazer à mão.\n\nAgora, junto com o aviso, chega a proposta de cura: o sistema prepara sozinho o desfazimento da entrega que quebrou e o coloca na fila da esteira, com todos os testes rodando por cima. Primeiro apaga o fogo, depois investiga — que é a regra da casa para emergência desde sempre.\n\nO que me deu mais trabalho não foi fazer ele desfazer: foi ensinar ele a NÃO desfazer. São quatro recusas, e cada uma é um jeito de a automação estragar o que tentava consertar: não desfaz o que não é uma entrega inteira; não desfaz um desfazimento (senão vira laço infinito); não abre um segundo pedido para o mesmo problema; e se o desfazimento der conflito, ele para e chama gente — resolver conflito sozinho é inventar código sem ninguém olhando.\n\nUma automação que desfaz demais é pior que nenhuma: ninguém confia, e todo mundo desliga.\n\nDetalhe bonito: enquanto eu escrevia, um guarda antigo da casa me reprovou por eu ter usado um atalho que esconde erro. Ele estava certo — troquei por uma versão que pergunta e diz a resposta.\n\nTerceiro degrau da Onda 6.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/PRNUM. 8 guardas novos sobre o job de reversao (as quatro recusas, o PR em vez de push, o pedido de pouso e o token que faz os checks rodarem). 819 testes verdes.",
  verificado_em: "2026-08-29",
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
