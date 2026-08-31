(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-005-o-robo-ganhou-o-botao-de-esvaziar-a-caixa-como-voce-pediu",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "O robô ganhou o botão de esvaziar a Caixa, como você escolheu, com uma trava que o impede de virar arma no futuro",
  detalhe: "Você escolheu que o robô apagasse as 2 ideias que sobraram, em vez de olhá-las você mesmo pelo Admin. O caminho para isso não existia: até hoje, apagar uma ideia só era possível clicando no botão da tela. Agora existe, e é um passo do pipeline.\n\nO QUE \"APAGAR\" SIGNIFICA AQUI, para não haver mal-entendido: é a mesma coisa que o seu botão \"Apagar definitivamente\" faz desde sexta. O título, o texto e a solução viram vazio; os votos e os comentários de todo mundo que participou somem de verdade. Ninguém alcança aquele conteúdo de novo, nem por link direto. Não tem restauração.\n\nA DECISÃO DE ENGENHARIA QUE VALE CONTAR: eu podia ter escrito de novo, dentro do passo novo, a mesma sequência que o botão executa. Seria mais rápido. Seria também a semente de um problema silencioso: no dia em que a regra do apagamento mudasse, o botão mudaria e o passo continuaria apagando pela regra velha, sem nenhum erro na tela. Então a regra saiu de dentro do botão para um lugar só, e os dois passaram a chamar o MESMO trecho. Um teste vigia isso e reprova quem escrever uma segunda cópia.\n\nA TRAVA, E ELA É A PARTE MAIS IMPORTANTE. Este é o único botão desta casa que destrói. Todos os outros semeiam, e dá para desfazer. Um botão de destruir a Caixa inteira, parado no pipeline, é uma arma carregada apontada para o futuro: a turma entra hoje, e daqui a um mês um clique distraído levaria quarenta ideias de aluno de uma vez, sem ninguém ter lido nenhuma.\n\nPor isso ele exige um número: quantas ideias quem dispara ESPERA apagar. Se a realidade não bater exatamente, ele para e não toca em nada. Repare que isso é diferente de perguntar \"tem certeza?\" — a pergunta mede a intenção de quem clica, e o número mede o estado do mundo no instante do clique. Quem acertou o número ontem erra hoje, se o mundo mudou no meio. É de propósito.\n\nO PASSO SEGUINTE é meu: com isto no ar, eu rodo o botão e apago as 2. Registro o resultado quando estiver feito.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/674 — suíte da célula sugestoes 509/509 verdes (eram 497 mais 12 novos), com Postgres 17 local, a mesma imagem do CI. Prova vermelho para verde da trava: quebrando de propósito a comparação do número, 3 testes REPROVARAM (a saída mostrou 'ESVAZIAMENTO OK' onde devia haver recusa); restaurada, 12/12 verdes. freeze-de-contrato PASS com o contrato IDÊNTICO ao congelado (947 linhas), provando que a refatoração não mexeu na API. black, bash -n, parse do YAML e ci/travessao.py todos PASS.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-002-sobraram-2-ideias-na-caixa-que-nao-sao-da-demonstracao",
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
