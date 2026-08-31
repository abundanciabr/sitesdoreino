(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-004-plano-sequencias-de-mensagens",
  tipo: "pendencia",
  quando: "2026-08-30",
  titulo: "Plano das mensagens automaticas para os alunos: pronto, e faltam 4 escolhas suas",
  detalhe: "Voce pediu sequencias de mensagens automaticas para os alunos — boas-vindas depois do cadastro, incentivo depois de outros acontecimentos. O plano esta escrito em docs/decisoes/PLANO-SEQUENCIAS-DE-MENSAGENS.md.\n\nA boa noticia: quase tudo ja existe. A caixa de avisos dentro do site (o sininho) esta no ar e funcionando; o encanamento de eventos roda em cinco celulas; a ficha do aluno ja guarda e-mail e WhatsApp. O que falta e um motor que entenda TEMPO — hoje a plataforma so sabe reagir na hora, nao sabe esperar dois dias e checar se ainda faz sentido mandar.\n\nO que o plano propoe: uma celula nova chamada jornadas, que DECIDE quem recebe o que e quando; o sininho continua mostrando dentro do site; e a celula mensageria passa a entregar por fora. Cada sequencia vira linha de tabela editavel na area administrativa, nao codigo — assim voce troca o texto de uma mensagem sozinho, a qualquer hora.\n\nUm aviso honesto: o envio de e-mail da plataforma NUNCA funcionou de verdade. O codigo que deveria mandar so escreve no log — esta escrito la, com todas as letras: 'Stub: loga o envio'. Ligar e-mail para valer e construir o envio, nao apertar um botao: precisa de conta em provedor, dominio remetente e configuracao de DNS. Os sete primeiros degraus do plano nao dependem disso e ja poem as sequencias no ar pelo sininho.\n\nAs quatro escolhas que sao suas estao no paragrafo 8 do plano: (1) por onde as mensagens saem — so sininho, ou e-mail tambem; (2) nasce a celula jornadas; (3) as sequencias sao dado editavel ou codigo; (4) aluno abaixo de 13 anos recebe direto ou o responsavel recebe.",
  autoridade: "sessao",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,

  se_eu_nao_decidir: "Nada e construido. As mensagens automaticas nao existem hoje de forma nenhuma — nem boas-vindas, nem incentivo — e nenhum robo comeca sem estas quatro respostas, porque criar celula e reabrir a porta do e-mail sao decisoes suas por lei do projeto.",
  recomendacao: "Comecar pelos degraus 1 a 7 (as sequencias no ar pelo sininho, dentro do site): custo zero, nenhum provedor, e ja resolve boas-vindas e incentivo. O e-mail entra logo em seguida, nos degraus 8 e 9, quando voce escolher o provedor — nao e cortar escopo, e a escada segura ate o completo.",
  reversivel: true,
  impacto: "alto"
});})();
