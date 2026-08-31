(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-012-o-numero-do-sininho-ainda-conta-o-recado-que-a-tela-nao-mostra",
  tipo: "pendencia",
  quando: "2026-08-31",
  titulo: "Sobrou uma ponta do conserto dos avisos: o numerinho do sininho ainda conta um recado que a tela já não mostra",
  detalhe: "O conserto de hoje tirou da tela o recado de ideia apagada. Mas o numerinho vermelho ao lado do sino é calculado em OUTRO lugar: quem responde \"quantos não lidos você tem\" é o serviço central de avisos, e ele continua contando a carta que a tela decidiu não mostrar.\n\nO QUE ISSO CAUSA NA PRÁTICA: o sino pode dizer 1, você clica, e a lista abre sem nada. Nenhum dado se perde e nada quebra; é uma discordância entre um número e uma lista, e é exatamente o tipo de coisa que esta casa persegue por toda parte.\n\nPOR QUE EU NÃO CONSERTEI JUNTO: para o número parar de contar, o serviço central precisa aprender uma operação que ele não tem — retirar um recado. Ele hoje só sabe contar, listar, marcar um como lido e marcar todos. Ensinar uma operação nova a um serviço é mudança de CONTRATO, e contrato nesta casa só muda por um rito com você presente, nunca de passagem no fim de outra tarefa. Foi por isso que eu parei aqui em vez de emendar.\n\nO TAMANHO REAL DISSO HOJE: perto de zero. Você é a única pessoa que tinha aviso de uma ideia apagada, e a turma que entra amanhã começa com a caixa vazia. Isso só volta a importar no dia em que alguém apagar a ideia de um aluno que já tinha sido avisado.\n\nO ATALHO QUE EU RECUSEI, para você saber que existiu: dava para \"marcar como lida\" a carta em vez de retirá-la, usando uma operação que já existe. O número fecharia. Mas seria o sistema afirmando que a pessoa leu uma coisa que ela não leu — mentira gravada no banco para consertar uma soma. Preferi trazer a pergunta a você.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/678 — o PR do conserto, que corta na leitura; contracts/notificacoes.openapi.yaml tem exatamente 4 operações (obterResumo, listarAvisos, marcarUmaComoLida, marcarTodasComoLidas) e nenhuma de retirada",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: "O sino pode mostrar um número maior que a lista, no dia em que uma ideia de aluno já avisado for apagada. Ninguém perde dado e nada quebra; a tela é que fica estranha.",
  recomendacao: "Fazer o rito de contrato quando sobrar uma janela sua, sem pressa: ensinar o serviço central a retirar um recado. É a única forma de o número e a lista nunca discordarem. Não recomendo o atalho de marcar como lida: fecha a conta mentindo.",
  reversivel: true,
  impacto: "baixo"
});})();
