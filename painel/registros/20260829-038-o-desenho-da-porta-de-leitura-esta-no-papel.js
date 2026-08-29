(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-038-o-desenho-da-porta-de-leitura-esta-no-papel",
  tipo: "pendencia",
  quando: "2026-08-29",
  titulo: "Você perguntou se cabia uma API no sistema — o desenho está no papel, e falta só a sua escolha",
  detalhe: "Você perguntou se não seria melhor criar uma API para as células consumirem, e escolheu ver o desenho no papel antes de qualquer coisa ser construída. O desenho está pronto no PR 518, e nenhuma linha do site mudou.\n\nA resposta curta: a sua pergunta são três perguntas. Entre as células do produto, essa API já existe e é lei desde o começo — as 13 células só conversam por contrato congelado. Para os robôs, ela nasceu no mesmo dia em que você perguntou: a fila de trabalho (PR 515). E para as telas, isso foi decidido um dia antes, na consultoria da Central de Orquestração, com três pareceres externos: nenhum banco novo, nenhum servidor novo.\n\nSobrou um pedaço de verdade na sua intuição, e ele é pequeno: a aba 'Os robôs' vai perguntar ao GitHub, direto do seu navegador, quem está com o quê agora — e o GitHub responde de graça só 60 vezes por hora para cada casa. Numa olhada de vez em quando, cabe folgado. Numa tela que fica aberta se atualizando sozinha, aperta. O remédio existe, é pequeno e já tem irmão funcionando no painel, mas ninguém mediu ainda se o aperto acontece de verdade.\n\nMinha recomendação é construir a aba do jeito que já foi decidido, com uma costura que deixe trocar isso depois em um PR pequeno, e medir três números antes de decidir. Construir o remédio antes de medir a dor é o erro que este projeto já catalogou.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/518",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: "Nada quebra e nada anda: a aba 'Os robôs' já está na fila como TAR-002, esperando a TAR-001. Ela nasce no desenho decidido, sem porta de leitura, se ninguém disser o contrário.",
  recomendacao: "Seguir o desenho já decidido — construir a aba sem porta de leitura, com a tomada isolada (um lugar só no código dizendo de onde vem cada bloco), e medir três números antes de decidir a porta. Não é economia de esforço: é que a decisão de ontem foi tomada com três análises externas e o código real, e nada mudou desde então que a contradiga.",
  reversivel: true,
  impacto: "medio"
});})();
