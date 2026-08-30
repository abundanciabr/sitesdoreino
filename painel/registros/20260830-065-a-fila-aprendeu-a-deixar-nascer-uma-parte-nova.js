(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-065-a-fila-aprendeu-a-deixar-nascer-uma-parte-nova",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A lista de tarefas dos robos nao deixava nascer uma parte nova do site; agora deixa",
  detalhe: "Assim que voce aprovou a gamificacao, tentei colocar a primeira tarefa dela na lista dos robos. A lista recusou.\n\nO motivo, em portugues: existe um guarda que confere se toda tarefa aponta para uma pasta que existe de verdade. Ele foi feito para pegar dois erros comuns: alguem escreveu o nome errado, ou alguem renomeou uma pasta sem avisar a lista. Ele nao previa um terceiro caso, que nao e erro nenhum: a tarefa que CRIA a pasta. A pasta da gamificacao nao existe justamente porque ninguem a construiu ainda, e a tarefa que iria construi-la era recusada por dizer o nome dela.\n\nO efeito era maior do que parece: enquanto isso durasse, NENHUMA parte nova do site poderia nascer pela lista de tarefas. A lista foi criada ontem, num momento em que todas as partes ja existiam, e a primeira parte a nascer depois dela topou com essa parede.\n\nO conserto e uma porta estreita de proposito. A tarefa agora pode dizer, por escrito, quais pastas ela vai criar; so isso a dispensa da conferencia, e so para aquilo que ela assumiu. Nome digitado errado continua sendo recusado, pasta renomeada continua sendo recusada, e dizer que vai criar uma coisa nao perdoa o nome errado de outra. Ha um teste para cada um dos tres casos.\n\nNada disso e visivel para voce no site. E encanamento, e ele estava impedindo a obra que voce acabou de aprovar de comecar.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/625 (este PR). PROVA VERMELHO->VERDE por assercao, sem rede: uma tarefa temporaria declarando toca=[gamificacao] sem o campo novo deixa o guarda em '1 failed'; a MESMA tarefa com cria=[gamificacao] devolve '1 passed'. MEDICAO DE FORA, no GitHub: o PR 624 reprovou na muralha com a mensagem crua 'toca apontando para caminho que nao existe: TAR-031: gamificacao, TAR-032: gamificacao'. Suite completa de ci/tests: 1287 passed. Aprendizado em armadilhas/221; documentado em fila/LEIA-ME.md. Caminho CODEOWNERS tocado e anunciado: ci/.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
