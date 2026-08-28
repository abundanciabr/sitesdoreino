(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-045-o-servidor-passou-a-dar-o-numero-em-vez-de-adivinhar",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "Dois robôs não conseguem mais pegar o mesmo número — quem chega em segundo é recusado na hora",
  detalhe: "A Onda 2 está no ar, e ela mata o problema que mais me atrapalhou hoje: cinco vezes dois robôs escolheram o mesmo número ao mesmo tempo, e cada vez custou refazer trabalho.\n\nA causa nunca foi descuido. Era adivinhação: o robô olhava a pasta, via qual número estava livre, e escrevia. Entre olhar e gravar existe uma janela — e outra sessão cabe dentro dela. Todo mundo fazia certo e colidia mesmo assim.\n\nAgora o robô não escolhe: ele PEDE. O próprio servidor do GitHub entrega o número, e quem chega em segundo recebe uma recusa imediata em vez de descobrir o estrago depois. É o mesmo mecanismo que impede duas pessoas de salvarem por cima uma da outra — só que aplicado ao número.\n\nO mesmo cofre serve para o robô anunciar 'estou pegando isto agora', com prazo de validade dentro. É o começo da cura para outro problema da lista: duas sessões construindo a mesma coisa sem saber uma da outra. Essas reservas aparecem no boletim que toda sessão lê ao abrir — sem leitor, o anúncio não serviria para nada.\n\nUma coisa que só apareceu porque eu testei o mecanismo ANTES de construir em cima dele: existe um jeito de essa trava parecer funcionar sem funcionar. Se dois robôs montarem um pedido idêntico, o servidor responde 'já está tudo certo' para os DOIS, sem conferir nada — e ambos sairiam achando que ganharam. A defesa é fazer cada pedido carregar uma marca única, e o código agora trata aquele 'já está tudo certo' como erro, nunca como vitória. Uma trava que devolve sucesso sem conferir é pior que trava nenhuma, porque é acreditada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/383. Primitivo provado contra o servidor REAL antes de uma linha ser escrita: criar a ref => '[new reference]' exit 0; segunda sessao na MESMA ref => '! [rejected] (stale info)' exit 1; MESMO commit reempurrado => 'Everything up-to-date' exit 0 (o falso-vencedor, que originou a defesa do nonce); com nonce => rejeitado, exit 1. Alocacao ao vivo devolveu 040 e depois 041, numeros diferentes. Suites: 46 verdes (14 do cofre + 32 do boletim). Prova por sabotagem, duas mutacoes: tirar o nonce => 1 vermelho; tratar rede caida como 'ocupado' => 1 vermelho. Restaurado, verde.",
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
