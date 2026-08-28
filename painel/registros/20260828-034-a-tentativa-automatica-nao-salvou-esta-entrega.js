(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-034-a-tentativa-automatica-nao-salvou-esta-entrega",
  tipo: "incidente",
  quando: "2026-08-28",
  titulo: "O servidor recusou o robô mais uma vez — e desta vez as três tentativas automáticas não bastaram",
  detalhe: "O servidor recusou a conexão do robô na hora de subir a versão nova. Nada saiu do ar: quando isso acontece, a versão anterior continua atendendo normalmente, e a nova simplesmente não sobe.\n\nO FATO NOVO NÃO É A RECUSA, É QUE O CONSERTO DE HOJE NÃO PEGOU. De manhã entrou a melhoria que faz a entrega tentar de novo sozinha (três vezes) antes de declarar vermelho. Nesta entrega as TRÊS tentativas falharam, uma atrás da outra, e só uma repetição pedida à mão fez passar — na primeira vez, sem mudar nada.\n\nISSO NÃO SIGNIFICA QUE A MELHORIA FOI INÚTIL: ela já salvou entregas antes desta hoje, e sem ela esta teria falhado do mesmo jeito, só que mais cedo. O que o dado mostra é que a janela em que o servidor fica inacessível às vezes é MAIOR do que as três tentativas cobrem.\n\nPOR QUE NÃO ESTOU TE PEDINDO NADA: não dá para consertar isto de dentro — o robô não tem acesso ao servidor, por lei do projeto — e a causa provável está no caminho entre a nuvem do GitHub e a máquina, não na máquina, que respondeu normalmente o tempo todo. O que muda de figura, e aí vira pedido seu: se a repetição à mão passar a falhar também, ou se uma entrega ficar pela metade.\n\nDepois da repetição, a entrega concluiu com sucesso e a versão nova está no ar — conferida de fora, na internet pública.",
  autoridade: "github",
  evidencia: "Run 33196295372 (deploy da célula admin, disparado pelo merge do PR https://github.com/abundanciabr/sitesdoreino/pull/369): as três tentativas falharam com 'dial tcp ***:22: i/o timeout', a última às 17:52:12. Repetido com gh run rerun --failed, sem nenhum merge novo, e concluído completed/success — lido por gh run view --json status,conclusion, nunca pelo código de saída de um comando com pipe. Prova de fora durante e depois: meshcraft.top/forms/sugestoes/ e /forms/sugestoes/gestao responderam 302 e a folha de estilo respondeu 200 o tempo todo.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
