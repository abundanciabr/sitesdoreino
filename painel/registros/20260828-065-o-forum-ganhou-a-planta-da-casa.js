(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-065-o-forum-ganhou-a-planta-da-casa",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O fórum ganhou a planta da casa — e ela foi desenhada para poder ser trocada um dia",
  detalhe: "Segundo degrau do fórum. Ainda não tem tela; o que entrou foi o modelo de dados — como as conversas ficam guardadas.\n\nPOR QUE ISSO É A PEÇA MAIS IMPORTANTE ATÉ AGORA: a forma escolhida é a comum de qualquer fórum do mundo — área, dentro dela tópicos, dentro deles mensagens. Não foi falta de imaginação. É o que mantém aberta a porta de, um dia, mudar para o Discourse se a escola crescer muito: sair de um formato normal é caminho conhecido, com ferramenta pronta; sair de um formato inventado aqui seria começar do zero. Foi o único ponto em que os dois consultores externos concordaram sem ressalva.\n\nTRÊS COISAS QUE FICARAM TRAVADAS POR TESTE:\n\n1. A CONTA DE 'LI ATÉ AQUI'. O jeito óbvio — guardar uma marca para cada mensagem que cada pessoa leu — faria, com 200 alunos e 20 mil mensagens, milhões de linhas só para responder 'tem coisa nova?'. O fórum guarda UMA marca por pessoa por área, como o Discourse faz. Tem teste que cria 30 mensagens e exige uma linha só.\n\n2. A BUSCA JÁ NASCEU PRONTA para ser rápida. Se ela fosse deixada para depois, instalar viraria uma operação na maior tabela do sistema.\n\n3. QUEM PODE ENTRAR EM CADA ÁREA É INFORMAÇÃO, NÃO CÓDIGO. Criar uma área nova — pública, só de alunos, ou trancada numa turma — é preencher uma linha, não pedir uma entrega de programação. E o padrão é o FECHADO: área nasce só para alunos. Abrir é um ato explícito, nunca o que acontece por esquecimento.\n\nUMA DESCOBERTA QUE VALEU O DIA: rodei os testes contra um banco de dados de verdade antes de entregar, e descobri que a busca em português tem dois buracos. Quem escrever 'modelagens' não acha 'modelagem', e quem escrever 'chapeu' sem acento não acha 'chapéu'. O segundo é o caro — no Brasil quase ninguém acentua ao buscar. Os dois estão anotados e travados em teste: quando a correção chegar, o teste avisa. Se eu tivesse usado um banco de mentirinha, teria entregue uma afirmação errada como se fosse verdade.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/415. MERGED em 28/08/2026. Suite: 18 verdes contra PostgreSQL 17 REAL (container local), nao SQLite. black limpo em 15 arquivos. PROVA POR SABOTAGEM: pendurar Mensagem.area => guarda da forma comum VERMELHO; area nova nascer PUBLICA => guarda do padrao fechado VERMELHO; restaurado => 18 verdes. Licao da busca em portugues registrada em armadilhas/154. Numero deste registro alocado pelo servidor via ci/reservar.py.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: true,
  impacto: null
});})();
