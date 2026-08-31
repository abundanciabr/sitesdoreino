(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-021-era-so-voce-o-unico-aviso-orfao-foi-apagado",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Respondendo a sua pergunta: era só você. O único aviso órfão da plataforma foi apagado",
  detalhe: "Você perguntou se outras pessoas também tinham avisos de ideias apagadas. A limpeza rodou e a resposta é: NÃO. Havia exatamente 1 aviso órfão na plataforma inteira, e ele era o seu.\n\nOS NÚMEROS, lidos do banco antes de qualquer coisa ser apagada: 2 ideias apagadas na Caixa; 1 aviso sobre elas; 1 pessoa afetada; 0 deles ainda não lidos. Depois da limpeza: 0 avisos órfãos restantes, conferido por uma segunda pergunta ao banco, feita por fora do comando que apagou.\n\nPOR QUE O NUMERINHO DO SINO NÃO PRECISOU DESCER: o seu aviso já estava marcado como lido, e o número só conta os não lidos. Então não havia o que descontar, e o comando registrou isso corretamente como zero descontos, em vez de cavar um buraco no contador.\n\nO CAMINHO COMPLETO desta correção, para o histórico: primeiro a tela parou de MOSTRAR recado de ideia apagada; depois a caixa central de avisos aprendeu a RETIRAR, coisa que ela nunca soube fazer; por último a limpeza rodou. As três coisas subiram hoje, com os deploys conferidos um a um.\n\nO que fica daqui para frente: se alguma ideia de aluno for apagada, o recado dele some junto, sozinho. Isso não depende mais de ninguém lembrar.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/actions/runs/33388147857 — workflow limpar-avisos-orfaos, lido por gh run view --json status,conclusion: completed/success. Prova pelo banco no passo 'Provar pelo banco': 2 ideias apagadas; SIMULAÇÃO antes de tocar em nada com 1 carta, 0 não lidas, 1 pessoa afetada, 0 arquivadas; 'RETIRADA OK: 1 carta(s) apagada(s) de 1 pessoa(s), 0 do arquivo, 0 desconto(s) no contador'; conferência de fora com 0 cartas órfãs restantes; linha 'PRONTO.'. As duas entregas que tornaram isso possível: https://github.com/abundanciabr/sitesdoreino/pull/678 (deploy-celula run 33387188335 success no job sugestoes) e https://github.com/abundanciabr/sitesdoreino/pull/684 (deploy-celula run 33387744361 success no job notificacoes).",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
