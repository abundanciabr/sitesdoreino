(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-010-voce-achou-o-recado-que-sobrou-de-uma-ideia-apagada",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "Você achou um recado que sobrou de uma ideia apagada, e estava certo: eu tinha limpado o quadro e esquecido o aviso",
  detalhe: "Você apontou duas coisas depois do esvaziamento: uma sugestão ainda aparecendo, e a notificação dela ainda no seu perfil. Fui conferir no código em vez de chutar, e você estava certo na segunda: era um buraco de verdade, e era meu.\n\nO QUE ACONTECIA, sem tecniquês: apagar uma ideia destrói o texto dela, mas o recado que já tinha SAÍDO sobre ela continuava na sua caixa de avisos. E como o título tinha virado vazio, o cartão aparecia sem nome nenhum, com a justificativa da equipe ainda escrita ao lado, e um link que não levava a lugar nenhum. Ou seja: a promessa que você assinou na sexta (\"que ela desapareça até para quem a criou\") não estava sendo cumprida do lado de quem recebeu o aviso.\n\nPOR QUE ISSO ESCAPOU: a caixa de avisos não mora dentro da Caixa de Sugestões. É um serviço separado, que guarda os recados de toda a plataforma, e ele só sabe fazer quatro coisas: contar, listar, marcar um como lido e marcar todos. NÃO existe \"retirar um recado\". Então apagar a ideia não tinha como alcançar o recado.\n\nO CONSERTO, em duas metades: a cópia do aviso que mora dentro da Caixa passou a ser destruída junto com a ideia; e a tela de avisos passou a NÃO MOSTRAR recado de ideia apagada. Na prática, o cartão some da sua tela assim que isto subir.\n\nO QUE EU TIVE CUIDADO DE NÃO QUEBRAR: o sumiço é cirúrgico. Recado de ideia apenas ARQUIVADA continua aparecendo, porque arquivar dá para desfazer e o texto está inteiro. Recado de outro assunto (matrícula, por exemplo) não é tocado. E recado de uma ideia que esta Caixa não conhece continua aparecendo com o aviso de que não achou — sumir com ele seria esconder um recado de verdade só porque eu não sei lê-lo.\n\nUMA COISA QUE O TESTE ME ENSINOU NO CAMINHO, e vale registrar: um dos testes vizinhos estava passando pelo MOTIVO ERRADO. Ele só cobrava que uma frase NÃO aparecesse na tela, e estava lendo a página de erro do sistema, onde de fato nenhuma frase aparece. Verde sem medir nada. Corrigi para ele cobrar presença, não ausência.\n\nSOBRE A PRIMEIRA COISA QUE VOCÊ VIU (a sugestão ainda aparecendo): essa eu não consegui reproduzir no código. A tela de gestão pede as ideias já sem as apagadas, e o banco confirma que não sobrou nenhuma com conteúdo. A explicação mais provável é que a página estava aberta desde antes da limpeza. Se depois de recarregar ela continuar lá, me diga: aí é outro buraco e eu vou atrás.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/678 — suíte da célula sugestoes 518/518 verdes (eram 509 mais 9 novos), Postgres 17 local. Prova vermelho para verde: desfazendo a linha que filtra os recados de ideia apagada, 2 testes REPROVARAM (o recado voltou a aparecer e a justificativa da equipe voltou a ser legível); restaurada, 9/9 verdes. freeze-de-contrato PASS com o contrato IDÊNTICO ao congelado (947 linhas). black PASS em 104 arquivos.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
