(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-007-preciso-saber-como-um-aluno-entra-na-escola",
  tipo: "pendencia",
  quando: "2026-08-28",
  titulo: "Preciso de voce: como um aluno entra na escola, e o que muda quando voce o aprova?",
  detalhe: "A tela de alunos ja existe (registro logo acima), e tres dos quatro tipos so dependem de trabalho de robo. O quarto — \"aguardando aprovacao\" — nao depende: ele depende de voce, porque hoje ele nao existe em lugar nenhum do sistema.\n\nO QUE EXISTE HOJE, em uma frase: quando alguem entra no site com a conta Google, o sistema guarda quem a pessoa e, e mais nada. Nao ha fila de espera, nao ha o gesto de aprovar, e nao ha nada que a aprovacao possa liberar — a escola ainda nao tem aula publicada.\n\nSAO DUAS PERGUNTAS, e a segunda so faz sentido depois da primeira:\n\n1. QUEM ENTRA NA FILA DE ESPERA? Tres caminhos possiveis. (a) Todo mundo que entrar no site com a conta Google aparece na fila — nao custa nada a mais para a pessoa, e voce ve todo interessado; em compensacao a lista enche de curiosos que so espiaram o site. (b) So quem preencher um formulario de inscricao da escola — uma peneira natural, so entra quem quis mesmo, mas e uma tela a mais para construir e um passo a mais para a pessoa. (c) Ninguem: todo mundo entra direto, sem aprovacao — nesse caso a tela de alunos passa a ter tres tipos, nao quatro, e nada disso precisa ser construido.\n\n2. O QUE A APROVACAO LIBERA? Enquanto nao houver aula publicada, aprovar so pode significar \"marcar como aluno\". Isso pode ser suficiente por agora (voce ja consegue ver e organizar quem entrou), ou pode ser cedo demais para construir — talvez faca mais sentido esperar a primeira aula existir, para que aprovar tenha consequencia de verdade no mesmo dia em que nascer.\n\nENQUANTO VOCE NAO RESPONDER, nada disso e construido — e a tela de alunos diz na cara, em vez de fingir que o numero e zero. Nao ha pressa mecanica nenhuma: nada esta quebrado esperando.",
  autoridade: "mantenedor",
  evidencia: "A tela que carrega este pedido esta em meshcraft.top/admin/escola/alunos/, entregue no PR https://github.com/abundanciabr/sitesdoreino/pull/339 — o tipo 'Aguardando aprovacao' aponta para esta caixa. Conferido em 28/08/2026 que nenhuma celula do projeto guarda estado de aprovacao de aluno: services/identidade guarda so quem a pessoa e (uma tabela, Identidade), e services/alunos guarda matricula com estado ativa/suspensa/reembolsada, criada por evento de pagamento — nao ha 'pendente' em lugar nenhum.",
  verificado_em: "2026-08-28",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null
});})();
