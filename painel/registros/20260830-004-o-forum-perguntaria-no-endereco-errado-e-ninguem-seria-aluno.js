(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-004-o-forum-perguntaria-no-endereco-errado-e-ninguem-seria-aluno",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "Achei e consertei um defeito que teria deixado o fórum sem reconhecer nenhum aluno",
  detalhe: "O fórum precisa perguntar a outra parte do sistema se a pessoa é aluna. Ele estava perguntando no endereço errado — faltava um pedaço do caminho.\n\nO que teria acontecido no ar: a pergunta voltaria sempre sem resposta, e o fórum, por segurança, trata \"não consegui conferir\" como \"não é aluno\". Resultado: NINGUÉM entraria em área de aluno, nunca. E o pior — nenhum erro apareceria em lugar nenhum, e o sinal de entrega ficaria verde. Um defeito que se disfarça de decisão de segurança.\n\nComo passou despercebido até agora: a célula tinha 39 testes verdes, mas o simulador de rede deles só conferia com QUEM o fórum falava, nunca em QUAL endereço. Um simulador que aceita qualquer caminho testa metade do trabalho.\n\nAgora ele confere o endereço inteiro, e um teste novo lê o contrato oficial do sistema para provar que o endereço montado é o que o contrato manda — prova vinda de fora, não a opinião de quem escreveu.\n\nProva: reintroduzindo o defeito de propósito, 8 testes ficam vermelhos; antes desta correção os 39 passavam com ele. Suíte completa contra banco de verdade: 53 passaram.\n\nO fórum continua fora do ar (ainda falta a parte elétrica). O defeito foi pego ANTES de chegar ao público.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/543",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
