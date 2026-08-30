(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-032-a-licao-da-area-que-o-semeador-nao-alcanca",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "A licao da area que o semeador nao alcanca",
  detalhe: "UMA ARMADILHA QUE QUASE DEIXOU O FORUM MENTIR PARA VOCE. Ao fechar as duas areas do forum ('Duvidas gerais' e 'Mostre seu trabalho'), o caminho curto era trocar duas palavras no arquivo que cria as areas. Os testes ficariam verdes, a entrega subiria — e NO SITE nada teria mudado: as areas continuariam abertas ao mundo.\n\nO motivo e simples de contar: aquele arquivo so age quando a area AINDA NAO EXISTE. Ele foi feito assim de proposito, para nao desfazer o que voce editar a mao um dia. So que as quatro areas ja nasceram na quinta-feira, entao ele nao alcanca nenhuma delas. E os testes rodam sempre num banco vazio, onde a diferenca nao aparece — o teste concordaria com o erro.\n\nO QUE FOI FEITO EM VEZ DISSO: uma instrucao de banco que roda sozinha quando a entrega sobe e fecha as areas que ja existem, ANTES de instalar a tranca. A ordem importa: com a tranca primeiro, a subida morreria no meio, no servidor, com o forum fora do ar. Foi medido e escrito assim de proposito.\n\nAs duas licoes ficaram guardadas onde o proximo robo vai tropecar nelas: a do semeador que nao alcanca, dentro da propria celula do forum; e a pegadinha de testar formulario nesta casa, na memoria de campo do projeto (armadilha 204). Nenhuma das duas precisa de nada de voce.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/586 — o PR que traz as duas licoes e o comprovante da tarefa TAR-019 no balcao da fila. A entrega em si esta no PR 585. A armadilha 204 foi achada ao vivo: o teste do formulario reprovou com 403 e a mensagem crua 'Forbidden (CSRF cookie not set.)' mesmo com o token no corpo do POST — a causa e o cabecalho cookie escrito a mao substituir o pote de cookies inteiro no cliente de teste do Django. Depois da correcao, os 21 testes do arquivo passaram.",
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
