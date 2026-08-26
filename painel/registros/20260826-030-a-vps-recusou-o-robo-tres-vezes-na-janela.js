(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-030-a-vps-recusou-o-robo-tres-vezes-na-janela",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "O servidor recusou a conexão do robô três vezes durante a entrega — sem um minuto de site fora do ar",
  detalhe: "O QUE ACONTECEU: na hora de colocar cada peça no servidor, a conexão do robô com a máquina expirou três vezes — uma na segunda entrega e duas seguidas na terceira. Cada uma virou uma tentativa nova, e todas as três peças acabaram entrando.\n\nO QUE NÃO ACONTECEU: o site não saiu do ar em momento nenhum. Conferi de fora durante a janela inteira — os três endereços responderam normalmente o tempo todo. Quando essa conexão falha, a versão nova simplesmente não sobe e a versão anterior continua atendendo. Ninguém que estivesse visitando percebeu nada.\n\nCOMO SEI QUE NÃO É PROBLEMA DA MÁQUINA: conferi do meu lado que o servidor estava respondendo na porta certa durante toda a janela. A máquina estava viva; o que falhou foi o caminho entre o robô da nuvem e ela. Detalhe importante porque existe uma falha ANTIGA com a mesma mensagem de erro, e aquela sim exigiria mexer numa configuração sua — não é o caso.\n\nO QUE FIZ ALÉM DE REPETIR: escrevi a diferença entre os dois casos na memória de campo (armadilhas/127), com a medição de uma linha que separa um do outro e a regra de quando parar de repetir e te avisar. A próxima sessão que topar com isso não vai gastar tempo suspeitando da configuração errada.\n\nNÃO PRECISA DE VOCÊ. Se voltar a acontecer com frequência, vira conversa sobre o provedor — por ora, foi ruído.",
  autoridade: "github",
  evidencia: "Runs 33013598246 (1 falha, verde no rerun) e 33014036704 (2 falhas, verde na 3a tentativa), ambos 'dial tcp ***:22: i/o timeout'; banner SSH-2.0-OpenSSH_9.6p1 respondendo do PC durante a janela; meshcraft.top/healthz, meshcraft.top e basileiatoutheou.org em 200",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
