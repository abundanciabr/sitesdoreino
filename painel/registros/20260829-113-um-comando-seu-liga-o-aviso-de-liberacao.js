(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-113-um-comando-seu-liga-o-aviso-de-liberacao",
  tipo: "pendencia",
  quando: "2026-08-29",
  titulo: "Um comando seu liga o aviso de liberacao — a ultima peca, e ela so pode ser feita por voce",
  detalhe: "O AVISO DE LIBERACAO ESTA CONSTRUIDO INTEIRO: quando voce libera alguem da fila, essa pessoa passa a receber um recado no sininho do site. Falta UM passo, e ele e seu — nao por escolha minha, e sim porque senha nao viaja pela esteira automatica (o deploy diz de si mesmo que JAMAIS toca nos arquivos de senha do servidor).\n\nPARA QUE SERVE: a parte que guarda os alunos conhece as pessoas pelo E-MAIL; o sininho entrega pelo NUMERO de plataforma. Para uma falar com a outra, as duas precisam compartilhar uma senha — e essa senha e gerada dentro do servidor, nunca por mim.\n\nCOLE ESTA LINHA DENTRO DA VPS (a janela onde o prompt comeca com deploy@srv... ou root@srv...):\n\n  curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-aviso-de-liberacao.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nELE NAO PERGUNTA NADA e nao pede nada. Gera a senha ali dentro, grava nos dois lados, confere que ficaram iguais, e recarrega as pecas. Termina em 'PRONTO: o aviso de liberacao esta ligado' — qualquer outro final comeca com 'PAROU POR SEGURANCA' e nao escreve nada. Rodar de novo e seguro: se a senha ja existir, ela e REUSADA, nunca trocada.\n\nSE VOCE NAO RODAR, NADA QUEBRA. A liberacao continua funcionando igual; so o aviso e que nao sai. A parte que guarda os alunos e fail-ABERTO nessa consulta de proposito: voce clicar em 'Liberar' e nada acontecer, por causa de uma peca de notificacao, seria muito pior que um aviso a menos.\n\nCOMO CONFERIR DEPOIS, em dois passos: (1) libere alguem da fila em /admin/escola/alunos/; (2) essa pessoa abre meshcraft.top e ve o numero no sininho, e dentro dele 'Sua situacao na escola mudou'.",
  autoridade: "sessao",
  evidencia: "As cinco pecas de codigo estao no ar ou na pista: PR #523 (o portao do CI aprendeu a medir contrato de evento), #524 (os contratos), #527 (a tela da Caixa aprendeu o aviso novo), #528 (a porta que traduz e-mail em id) e #530 (a celula dos alunos ganhou voz). O script infra/provisionar-aviso-de-liberacao.sh foi conferido com 'bash -n' e segue o mesmo desenho fail-closed do provisionar-pares-de-categorias.sh, que voce ja rodou com sucesso em 28/08/2026. O que EU nao consigo fazer daqui: escrever no /opt/plataforma/env/ da VPS — o agente nao tem SSH (Lei 5) e o deploy-infra nao toca em env.",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "curso",
  vence_em_dias: null
});})();
