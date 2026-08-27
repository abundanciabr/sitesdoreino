(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-042-a-vps-recusou-o-robo-pela-quarta-vez-hoje",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "O servidor recusou a conexão do robô pela quarta vez hoje — de novo sem tirar o site do ar",
  detalhe: "Mesma falha do registro 030, agora na entrega da trava de número repetido: a conexão do robô da nuvem com o servidor expirou na hora de subir a versão nova. Repeti a etapa sem mergear nada de novo e passou.\n\nO SITE NÃO SAIU DO AR. Conferi de fora durante a falha: tanto o site público quanto a área administrativa responderam normalmente o tempo todo. Quando essa conexão falha, a versão nova simplesmente não sobe e a anterior continua atendendo.\n\nO FATO NOVO NÃO É A FALHA, É A CONTAGEM. O registro 030 contou três vezes numa janela; esta é a quarta do mesmo dia. Uma falha que se conserta sozinha com uma repetição não vale o seu tempo — mas quatro num dia é padrão, e padrão vale ser medido antes de virar rotina que ninguém questiona.\n\nPOR QUE NÃO ESTOU TE PEDINDO NADA AINDA: não dá para consertar isto de dentro (o robô não tem acesso ao servidor, por lei do projeto), e a causa provável está entre a nuvem do GitHub e a máquina — não na máquina, que estava viva e respondendo durante toda a falha. Colocar isso na sua caixa hoje seria te entregar um problema sem ação possível do seu lado. O gatilho para virar pedido seu: se passar a acontecer com deploy PARADO no meio (versão nova que sobe pela metade) ou se a repetição deixar de resolver.",
  autoridade: "github",
  evidencia: "run 33032286871 — 'deploy (admin)' falhou com 'dial tcp ***:22: i/o timeout'; repetido com gh run rerun --failed e concluído completed/success, com 'painel embutido: 55 registros' no log; /admin/healthz e o site público responderam 200 durante a falha e depois dela",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
