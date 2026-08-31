(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-101-a-caixa-passa-a-dizer-quem-e-a-pessoa",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Segundo degrau: a Caixa de Sugestoes passa a dizer quem e a pessoa",
  detalhe: "Este e o conserto do cracha que eu te contei no registro anterior, e ele vem do lado de quem AVISA. A Caixa de Sugestoes agora manda, junto com cada aviso, o cracha GERAL da pessoa, e nao so o cracha interno dela.\n\nSao tres avisos que mudaram: alguem criou uma sugestao, alguem votou, e a equipe mudou o status de uma sugestao. Os dois primeiros passaram a dizer quem fez a acao. O de voto e o de status passaram a dizer tambem quem ESCREVEU a sugestao, que e uma pessoa diferente de quem votou e e ela quem deve receber o ponto na regra 'sua sugestao foi votada'.\n\nUM DETALHE QUE VALE A PENA VOCE SABER, porque ele mostra o cuidado: no aviso de voto, a regra que premia o AUTOR estava caindo no cracha de quem VOTOU, por falta de campo melhor. Ou seja, ela nao errava so o numero do cracha: errava a pessoa. Se tivesse sido ligada, quem votasse ganharia o premio de quem escreveu.\n\nO CRACHA VAI COMO OPCIONAL, e essa foi a decisao mais importante do degrau. Nao da para exigir. A propria Caixa decidiu, la atras, que nunca vai recusar ninguem por causa desse cracha, entao ele pode faltar em algumas linhas antigas. E o aviso nasce dentro da mesma operacao que cria a sugestao: se o campo fosse obrigatorio, CRIAR UMA SUGESTAO passaria a dar erro para quem nao tem o cracha. Preferi que o aviso saia sem ele e que quem recebe simplesmente nao credite, anotando o motivo. Nao pagar da para corrigir depois; pagar para a pessoa errada, nao.\n\nE UMA COISA QUE NAO PIOROU: votar continua custando o mesmo ao servidor. O cracha de quem escreveu ja vem junto na mesma consulta que a tela ja fazia, entao nao ha uma pergunta a mais ao banco a cada voto, que e o gesto mais repetido da Caixa.\n\nAINDA NAO HA NADA LIGADO. Faltam a parte das conquistas entender o cracha novo, e a sua tela de ligar e desligar.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/775, consumidor do rito https://github.com/abundanciabr/sitesdoreino/pull/773 (mergeado, commit 86a8a573). PROVA VERMELHO->VERDE sem rede, no guarda que existe para isto (tests/test_inv_envelope_casa_com_contrato.py): contra os contratos antigos, 4 failed (o campo novo nao era permitido, additionalProperties false); contra os contratos do #773, 13 passed. Suite da celula 518 passed. black --check limpo em 38 arquivos. O erro da PESSOA errada no aviso de voto foi lido no proprio codigo que emite o evento, onde o comentario diz 'autor_id e quem VOTOU, nao quem sugeriu', cruzado com a regra 'sugestao-votada' que pede o autor do alvo.",
  verificado_em: "2026-08-31",
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
