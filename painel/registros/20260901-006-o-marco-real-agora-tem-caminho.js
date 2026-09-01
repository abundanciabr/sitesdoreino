(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-006-o-marco-real-agora-tem-caminho",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "O que o aluno consegue na vida real agora tem caminho dentro da escola",
  detalhe: "Voce escolheu esta parte, e ela e a mais importante do sistema todo.\n\nO QUE MUDA: ate hoje a escola so sabia contar o que acontece DENTRO do site (ponto, nivel, comemoracao). O que o aluno consegue no mundo — a primeira obra terminada, o primeiro cliente, os primeiros dolares — nao tinha por onde entrar. Agora tem: o aluno manda a prova, alguem da escola olha e diz sim, e a conquista fica registrada com o nome de quem validou.\n\nO PRAZO E EM DIAS UTEIS, e isso e de proposito: 5 dias para um marco, 2 para uma resposta. Um pedido feito na sexta a noite nao vence no domingo, quando nao ha ninguem para atende-lo. Prazo que corre enquanto a escola dorme nao mede atraso, mede fim de semana — e uma fila que mostra atraso falso ensina a equipe a ignorar a cor vermelha.\n\nAS DEFESAS QUE EU COLOQUEI, e cada uma existe porque sem ela o sistema viraria o contrario do que promete:\n\n1. Ninguem valida o proprio marco. Um reconhecimento que a pessoa se da sozinha nao reconhece nada.\n2. Um colega nao fecha marco que envolve dinheiro. Quem assina isso e a equipe.\n3. Devolver um pedido exige escolher um motivo de uma lista curta ('falta a evidencia', 'nao da para ler', 'ainda nao cumpre o criterio', 'precisa de um adulto da equipe'). Nunca texto livre: um 'nao' com opiniao sobre o trabalho, vindo de um colega, e humilhacao com cara de processo.\n4. DUAS devolucoes vindas de colegas fazem o pedido subir obrigatoriamente para a equipe. Se um grupo combinar de recusar o trabalho de alguem, o caminho termina numa pessoa da escola. E automatico, porque depender de o aluno reclamar e depender justamente do que ele nao vai fazer.\n5. Reenviar corrigido reinicia o prazo, mas NAO zera o contador de devolucoes — senao a defesa acima seria facil de furar.\n6. A prova que o aluno manda (um print de pagamento, uma conversa com cliente) fica guardada em camada privada e NUNCA viaja no aviso.\n\nUMA COISA IMPORTANTE, e ela e regra sua ja escrita: marco real vale ZERO ponto. Se conseguir o primeiro cliente pagasse 500 pontos, o marco viraria mais um item do joguinho, e o aluno aprenderia a perseguir o numero em vez da coisa. Quem recusa o contrario e o proprio banco de dados.\n\nO QUE FALTA PARA VOCE VER ISSO FUNCIONANDO: as duas telas — a do aluno para enviar a prova, e a da equipe para decidir em um clique. Ja estao no balcao como proxima tarefa. Enquanto elas nao existem, uma devolucao e silenciosa: o aluno nao fica sabendo, porque avisar 'seu pedido voltou' seria uma ma noticia, e a regra da escola e que so boa noticia vira aviso.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/813. Suite da celula 191 passed (eram 171; 20 testes novos). PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), tres sabotagens: (1) desligada a trava do auto-julgamento, 'Failed: DID NOT RAISE ValidacaoRecusada'; (2) prazo contado em dias de calendario, 'AssertionError: assert datetime.date(2026, 9, 9) == datetime.date(2026, 9, 11)'; (3) anti-anel desligado, 'assert False is True' no campo escalado_para_adulto. ci/travessao.py PASS; ci/freeze-de-contrato.sh gamificacao PASS (contrato identico ao congelado, 406 linhas, e 4 operacoes com autenticacao conferida na fonte); black limpo. Nenhum arquivo de contracts/ tocado.",
  verificado_em: "2026-09-01",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
