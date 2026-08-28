(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-039-nenhum-robo-comeca-mais-sem-saber-o-que-mudou",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "Nenhum robô começa mais sem saber o que os outros estão fazendo e o que mudou nas últimas 24 horas",
  detalhe: "A Onda 1 está no ar. Ela ataca o problema mais grave que ainda não tinha trava nenhuma: robô decidindo com informação velha.\n\nAgora, ao abrir uma sessão, o robô recebe na cara um boletim lido do servidor na hora: quantas entregas esta cópia está atrasada, quem está mexendo em quê neste momento, o que entrou nas últimas 24 horas, e — em destaque — se alguma LEI do projeto mudou desde a última vez. Antes de pensar em qualquer coisa.\n\nE ele se RECUSA a começar se não conseguir falar com o servidor. Essa é a parte que faz diferença: um boletim pela metade tem a mesma cara de um boletim inteiro, e é assim que a informação velha se disfarça de informação atual. Ou sai completo, ou a sessão para e diz o que faltou.\n\nPor que isso importa tanto hoje: foi exatamente essa doença que fez eu contar uma coisa errada às cinco IAs consultadas. Uma frase antiga de uma lei do projeto, lida com toda sinceridade, virou premissa falsa — e três consultores gastaram parte da resposta projetando substitutos para uma proteção que já existia. Ler nunca dá erro: é isso que torna essa falha invisível.\n\nDe quebra, o boletim já mostra qual número está livre para o próximo registro e para a próxima lição do catálogo — que é a corrida que me pegou quatro vezes hoje. Ele avisa honestamente que isso NÃO é reserva: a trava de verdade é a Onda 2.\n\nUma nota sobre como isso foi construído: rodar a ferramenta contra o projeto de verdade revelou um erro meu que teste nenhum tinha pegado. Ela sugeria o número 1 para a próxima lição, quando o certo era 154 — e usar o 1 quebraria referências antigas. Só apareceu porque foi rodada no mundo real, e não só contra dados inventados.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/377. Suite ci/tests inteira: 639 passaram, 0 falharam (a base do dia era 617 + os 29 novos do boletim, menos os que o pytest agrupa). Prova por sabotagem, em duas mutacoes: (1) tirar a recusa de campo ausente do montador => 6 vermelhos; (2) fazer 'nao consegui perguntar ao GitHub' virar 'lista vazia' => 1 vermelho. Restaurado, 29/29 verdes. O erro do numero 154 foi achado rodando `python ci/boletim.py` contra o repositorio real e virou teste proprio.",
  verificado_em: "2026-08-28",
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
