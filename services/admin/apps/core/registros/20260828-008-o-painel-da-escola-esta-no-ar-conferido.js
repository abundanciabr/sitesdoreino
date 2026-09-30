(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-008-o-painel-da-escola-esta-no-ar-conferido",
  tipo: "medicao",
  quando: "2026-08-28",
  titulo: "O painel da escola esta no ar de verdade — e o servidor recusou o robo pela sexta vez antes de deixar",
  detalhe: "PODE ABRIR: meshcraft.top/admin/ agora mostra dois paineis, e meshcraft.top/admin/escola/alunos/ e a tela nova dos alunos. Esta e a confirmacao de que a entrega registrada acima chegou ao servidor — nao e a mesma coisa que mergear, e a diferenca ja mordeu este projeto antes.\n\nCOMO EU CONFERI, e por que nao aceitei o primeiro sinal: o container da area administrativa esta de pe e SAUDAVEL com a imagem nova, e os dois enderecos novos respondem de fora mandando para o login (que e o comportamento certo — a area so abre para o seu e-mail). O veredito veio da pergunta direta ao GitHub sobre o resultado do envio, e nao do fim de um comando com cano pendurado, que ja mentiu verde neste projeto.\n\nO TROPECO DO CAMINHO: o envio ficou VERMELHO na primeira tentativa, com o servidor nao atendendo a conexao do robo do GitHub. Pedi de novo e passou. E a SEXTA vez em tres dias — a quinta esta registrada logo acima, com o diagnostico completo e a proposta de conserto duravel (fazer a esteira tentar de novo sozinha antes de declarar vermelho). Registro esta aqui porque, quando o pedido de novo da certo, o GitHub sobrescreve a falha e o padrao some do historico: se ninguem contar a mao, ele fica invisivel.\n\nNAO abri pedido novo por isso — a pergunta ja esta na sua caixa, no registro anterior, e duas caixas para a mesma decisao e exatamente o que a lei desta casa proibe.",
  autoridade: "sonda",
  evidencia: "Deploy run 33177768222 (merge do PR 339, commit 424090aa): primeira tentativa FAILURE em 'dial tcp ***:22: i/o timeout'; apos 'gh run rerun --failed', conclusion=success conferido por 'gh run view --json status,conclusion'. No log do run: 'plataforma-admin-1 ghcr.io/abundanciabr/plataforma-admin:main ... Up 7 seconds (healthy)'. Medido de fora deste PC em 28/08/2026, depois do run verde: GET https://meshcraft.top/admin/healthz = 200; GET /admin/escola/ e /admin/escola/alunos/ = 302 para https://meshcraft.top/entrar/google com next=/admin/escola/ e next=/admin/escola/alunos/ respectivamente. Ocorrencia anterior do mesmo engasgo: 20260828-005 (que segue aberta na sua caixa).",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null
});})();
