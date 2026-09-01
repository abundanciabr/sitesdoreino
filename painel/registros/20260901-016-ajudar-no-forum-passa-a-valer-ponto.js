(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-016-ajudar-no-forum-passa-a-valer-ponto",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "Ajudar um colega no forum passa a valer ponto, e a primeira medalha ganha como cair",
  detalhe: "Esta e a outra metade do forum. Ele ja fala; agora a parte das conquistas escuta.\n\nTRES COISAS PASSAM A VALER PONTO (todas DESLIGADAS, esperando voce):\n\n- falar numa conversa: 5 pontos, ate 5 vezes por dia\n- abrir uma conversa: 8 pontos, ate 3 vezes por dia\n- TER A SUA RESPOSTA ACEITA: 50 pontos, sem limite\n\nDE ONDE SAEM ESSES NUMEROS: da sua propria lei, nao do meu gosto. A regra escrita na consultoria diz 'entrar no site vale zero; ser validado por outra pessoa vale cerca de dez vezes o normal'. Entao falar vale 5 (o piso) e ter a resposta aceita vale 50 — dez vezes. E de proposito que 50 e MAIOR que os 40 da sugestao implementada: quem ajudou de verdade recebe a maior recompensa da escola, porque isso e o que esta mais perto da vida real.\n\nOS DOIS PRIMEIROS TEM LIMITE DIARIO e o terceiro nao, e a razao e a mesma lei: escrever muito e volume, e a escola nao paga por volume. Ser reconhecido por outra pessoa nao se fabrica sozinho.\n\nSE VOCE QUISER OUTROS NUMEROS, e so dizer: eles sao dado, nao codigo. Eu mudo numa linha.\n\nA MEDALHA 'MAO AMIGA' AGORA TEM COMO CAIR, e ela e a primeira medalha automatica que esta escola consegue conceder de verdade. Uma coisa que fiz questao de separar: ela NAO depende de a regra de pontos estar ligada. Reconhecimento e uma coisa, pagamento e outra — se voce desligar a regra por uma semana, a medalha continua existindo.\n\nE UMA DEFESA QUE VALE EXPLICAR: a ajuda e contada pela MENSAGEM, nao pelo clique. Marcar, desmarcar e marcar de novo conta uma vez so. Sem isso, dois amigos combinados fabricariam a medalha em minutos alternando a marca. Junto com cada ajuda fica gravado QUEM marcou — nao para mostrar, mas para um dia dar para enxergar um combinado.\n\nDOIS BURACOS QUE OS TESTES ACHARAM, e os dois eram do tipo silencioso: (1) quem so ajudou e nunca ganhou ponto nenhum nao era avaliado, ou seja, a medalha nao caia justamente para quem mais a merecia; (2) um teste antigo cravava 'a escola tem 6 regras' e ia reprovar a cada regra nova — agora ele mede a lista de verdade.\n\nO QUE AINDA NAO ENTRA: quando a moderacao tira uma mensagem do ar, o ponto pago por ela ainda nao e devolvido. O forum ja avisa esse fato, e ele fica guardado; falta a parte das conquistas saber achar qual pagamento veio daquela mensagem. Esta declarado no codigo, com o motivo, para ninguem achar que funciona.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/822, completando o PR #821. Suite da celula 230 passed (eram 223; 7 testes novos). PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), duas sabotagens: com o motor esquecendo o campo do forum o premio para de sair ('ValueError: not enough values to unpack' no lancamento que deveria existir); com a ajuda so registrada quando a regra paga, 'AjudaAceita.DoesNotExist' e 'assert 0 == 1' no guarda que separa reconhecimento de pagamento. ci/travessao.py PASS, ci/freeze-de-contrato.sh gamificacao PASS, black limpo.",
  verificado_em: "2026-09-01",
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
