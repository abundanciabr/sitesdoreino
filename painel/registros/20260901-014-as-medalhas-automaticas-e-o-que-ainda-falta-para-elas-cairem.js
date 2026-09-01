(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-014-as-medalhas-automaticas-e-o-que-ainda-falta-para-elas-cairem",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "A escola aprendeu a conceder medalha sozinha, e eu preciso te dizer o que ainda falta",
  detalhe: "Esta era a metade que faltava do degrau que voce escolheu, e ela esta pronta: quando a conta de uma medalha bate, a escola concede sozinha, credita os pontos e os Cristais dela, e avisa a pessoa no sininho. Ligar uma medalha reconhece quem JA cumpriu, como voce decidiu hoje de manha.\n\nAGORA A PARTE QUE VOCE PRECISA SABER, e eu preferi medir antes de te dizer: DAS QUATRO MEDALHAS QUE A SUA ESCOLA TEM HOJE, NENHUMA VAI CAIR. Nao e defeito do que eu acabei de construir. E que cada uma delas conta uma coisa que o site ainda nao sabe registrar:\n\n- 'Fundador' nao tem conta nenhuma: e a equipe que concede, uma pessoa por vez. Sempre foi assim, de propósito.\n- 'Primeira obra' espera o site saber dizer que uma obra ficou pronta. Isso e a galeria, que e um degrau bem mais a frente.\n- 'Dez forjas' conta pecas seladas no medidor de esforco. O medidor (a Forja) ainda nao existe.\n- 'Mao amiga' conta respostas aceitas no forum. O forum esta no ar, mas ainda nao AVISA a parte das conquistas quando alguem ajuda alguem.\n\nEU CONFERI ISSO NO CODIGO, nao supus: procurei quem escreve cada uma dessas tabelas e nao achei ninguem. A sua tela avisa cada caso antes do clique, entao ligar uma delas nao vai te dar a impressão de que quebrou.\n\nO QUE ISSO SIGNIFICA NA PRATICA: o motor esta pronto e correto (tem teste que liga uma Forja de mentira e ve a medalha cair na hora), e o que falta sao os FATOS. O caminho mais curto para as medalhas comecarem a acontecer de verdade e o forum passar a avisar o que acontece nele — com ele, 'Mao amiga' passa a cair e ajudar um colega passa a valer ponto.\n\nUM ERRO MEU QUE VALE CONTAR: na primeira versao, uma medalha que destravava outra concedia as duas certas no banco mas devolvia so uma na resposta. Ninguem teria notado olhando a tela. Um teste pegou, e o conserto virou comentario explicando por que aquela trava fica ligada.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/820. Suite da celula 223 passed (eram 211; 12 testes novos). PROVA VERMELHO->VERDE POR ASSERCAO (armadilhas/195), duas sabotagens: removido o filtro de classe, o marco real passa a cair por conta ('assert [<Concessao: pes-aluno: 5>] == []'); removida a trava de reentrancia, a cadeia de medalhas devolve metade ('assert [dos-trezentos] == [do-nivel-dois, dos-trezentos]'). A MEDICAO que sustenta o aviso deste registro: varredura por `.objects.create` em services/gamificacao nao acha ninguem escrevendo Forja, Sequencia nem ProgressoDeMissao, e nenhum evento de forum chega a esta celula. ci/travessao.py PASS, ci/freeze-de-contrato.sh gamificacao PASS, black limpo.",
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
