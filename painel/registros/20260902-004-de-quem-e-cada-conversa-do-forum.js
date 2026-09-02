(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-004-de-quem-e-cada-conversa-do-forum",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "A parte das conquistas passou a anotar quem abriu cada conversa do forum",
  detalhe: "Os Destaques da semana sao a ideia de alguem da equipe escolher ate tres trabalhos por semana e escrever por que escolheu. Para isso funcionar faltavam duas pecas invisiveis, e as duas entraram hoje. Nenhuma tela mudou: este e o alicerce, e a tela de escolher os destaques vem no proximo passo.\n\nA primeira peca: quando alguem abre uma conversa no forum, a parte das conquistas agora ANOTA quem foi. Ate hoje ela recebia o aviso, somava o ponto e jogava fora a informacao de quem tinha sido. Isso importa porque, na hora de mandar a carta de parabens para o dono do trabalho destacado, o forum so sabe dizer o NOME que aparece na tela, e nome na tela nao serve de endereco. O identificador de verdade so viajava naquele aviso, e agora ele fica guardado.\n\nEla anota o minimo: de qual escola, qual conversa, quem abriu e quando. Nunca o titulo e nunca o texto, porque esses sao do forum, e ter uma copia aqui criaria uma segunda versao da verdade que ninguem manteria em dia.\n\nUMA COISA IMPORTANTE, PARA NAO PARECER DEFEITO DEPOIS: so da para destacar conversas abertas DEPOIS que esta entrega subir. As antigas a parte das conquistas nao conhece e nao ha como recuperar, porque o aviso delas ja passou e a economia esta desligada, entao nem o historico de pontos guardou rastro. Nao e bug, e o preco de a anotacao ter nascido depois do forum.\n\nE ela anota MESMO COM A ECONOMIA DESLIGADA, o que e a decisao mais importante desta entrega. Reconhecer alguem e uma coisa, pagar pontos e outra. Se a anotacao dependesse de as regras de pontos estarem ligadas, ela nasceria vazia e continuaria vazia, e a tela de destaques nasceria morta.\n\nA segunda peca: a parte das conquistas passou a poder PERGUNTAR ao forum quais sao as conversas mais recentes e como elas se chamam. O titulo nao vem no aviso de propósito (avisos carregam so identificadores, nunca texto de aluno), entao quem for escolher um trabalho precisa perguntar na hora de mostrar. Se o forum estiver fora do ar ou a senha de maquina nao estiver ligada, a resposta e uma lista vazia, e a tela desenha sem a lista. Nunca uma tela quebrada.\n\nFALTA UM PASSO SEU, e ele e uma linha so dentro da VPS: o script infra/provisionar-par-da-gamificacao-com-o-forum.sh. Ele liga a senha de maquina entre as duas partes do site (senha nao viaja pela esteira automatica, por lei do projeto). ATENCAO: ja existe um script de nome parecido no sentido contrario, que voce rodou para a etiqueta de nivel. Este e OUTRO, com senha propria. Enquanto ninguem rodar, nada muda e nada quebra: a tela de escolher os destaques, que vem no proximo passo, e que abre dizendo que ainda nao consegue falar com o forum.\n\nA suite da celula foi de 298 para 320 testes, todos verdes. Cada guarda foi provado quebrando o codigo de proposito e vendo o teste ficar vermelho: treze quebras deliberadas, e duas delas denunciaram testes meus que pareciam certos e nao mediam nada. Os dois foram consertados neste mesmo PR, e a licao virou entrada de catalogo para o proximo robo nao repetir.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/846",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
