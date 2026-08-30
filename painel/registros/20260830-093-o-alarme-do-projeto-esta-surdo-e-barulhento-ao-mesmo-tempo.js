(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-093-o-alarme-do-projeto-esta-surdo-e-barulhento-ao-mesmo-tempo",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "O alarme que protege os robos esta barulhento demais num lugar e surdo em outro, e os dois foram medidos hoje",
  detalhe: "O projeto tem um sino que avisa o robo quando ele esta prestes a repetir um erro ja conhecido. E uma das melhores pecas da casa, e hoje ela foi medida por dentro pela primeira vez. O resultado tem dois lados, e os dois importam.\n\nBARULHENTO. Das 45 assinaturas que o sino usa para reconhecer uma falha, 21 aparecem em texto comum do proprio projeto. Ou seja: quase metade delas toca quando um robo apenas LE o arquivo que escreve aquela mensagem, sem nada ter dado errado. Eu mesmo passei por isso quatro vezes hoje. Alarme que toca a toa e alarme que se aprende a ignorar, e ai ele para de proteger quando a falha for de verdade.\n\nEste caso e diferente dos dois consertados hoje. Naqueles, a assinatura estava errada e bastou apertar. Aqui a assinatura esta certa: o problema e que ninguem pergunta se aquilo saiu de uma falha ou de uma leitura. A cura ja tem meio caminho andado dentro do proprio codigo, e virou tarefa no balcao com o cuidado escrito de nao calar demais: calar demais troca barulho por cegueira, que e pior.\n\nSURDO. O sino que roda nesta maquina le a lista de assinaturas de um arquivo que e GERADO e nao viaja no Git. Como a pasta do seu computador esta centenas de entregas atrasada, essa lista tem 7 assinaturas em vez de 45, e ainda carrega a versao antiga de uma que foi consertada hoje. Na pratica: o conserto entrou na linha principal e NAO esta valendo aqui. E o mesmo defeito do espelho velho que ja virou tarefa, visto por outro angulo.\n\nNada disso afeta o site nem espera por voce.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/659 (este PR, que cria a TAR-048). O NUMERO foi medido pelo robo da TAR-043 varrendo as 210 entradas do catalogo contra o corpus de saidas saudaveis: 21 das 45 assinaturas casam texto benigno do repositorio. O lado surdo foi medido na mesma sessao: armadilhas/SINAIS.json e gerado e gitignored desde a TAR-022, o clone principal esta 375 commits atras, e o arquivo local tem 7 assinaturas, incluindo a versao pre-TAR-038 da entrada 185, que tocou duas vezes sobre saida benigna durante o trabalho. Liga-se ao registro 20260830-086 e a TAR-045.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
