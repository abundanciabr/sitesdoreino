(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-041-o-painel-estava-a-um-registro-de-travar-o-projeto",
  tipo: "incidente",
  quando: "2026-09-02",
  titulo: "O painel estava a UM registro de travar o projeto inteiro, e foi destravado",
  detalhe: "Achei isto por acidente, indo entregar outra coisa, e era serio.\n\nO QUE ESTAVA PRESTES A ACONTECER: o painel tem um limite de tamanho de proposito, e o proprio sistema se recusa a montar a pagina se passar dele. Hoje esse limite tinha ONZE BYTES de sobra. Como a lei da casa manda todo trabalho trazer o registro dele, o proximo registro de QUALQUER robo ia bater no limite e ser recusado, e ninguem mais conseguiria publicar nada. O projeto estava a um passo de parar, e nada na tela avisava.\n\nO QUE ESTAVA ENCHENDO O PAINEL: a caixa 'Atencao agora' mostra o que esta vermelho ou ambar e ainda sem resposta. Acontece que um incidente quase nunca ganha uma resposta escrita: ele e consertado, o conserto vira uma entrega, e o incidente fica ali para sempre. Resultado medido: um terco do painel inteiro era texto de incidente antigo, um deles com quatro paginas, varios de cinco dias atras.\n\nO QUE MUDA NA SUA TELA: em 'Atencao agora', os problemas mais antigos que os dez ultimos passam a aparecer como UMA LINHA (titulo, cor e data) em vez do texto inteiro. Nenhum some, todos continuam contados no cabecalho da caixa, e o texto continua a um clique, na Memoria. Os dez mais recentes seguem abertos como sempre.\n\nO QUE EU NAO FIZ, de proposito: nao aumentei o limite. A lei escrita no proprio arquivo diz que estourar e sinal de que alguma coisa real esta se acumulando, e que a resposta certa e olhar o acumulo. Foi o que fiz.\n\nSOBRA UMA PERGUNTA PARA VOCE, mas ela nao e urgente e nao esta bloqueando nada: incidente resolvido continua marcado como aberto no livro para sempre. Se um dia voce quiser que 'Atencao agora' mostre so o que de fato ainda esta doendo, isso vira uma conversa nossa.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/878. Medido antes: resumo 153589 bytes de um teto de 153600 (11 de folga), 49439 deles em incidentes abertos, e 100 de 100 registros viajando com texto completo. Medido depois: 131,4 KB com os MESMOS 100 registros. teste_logica.js e teste_gerador.js verdes; ci/muralha-do-painel.sh verde. Seis casos-guarda novos, provados por sabotagem: arrancar o teto deixa tres deles vermelhos.",
  verificado_em: "2026-09-02",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
