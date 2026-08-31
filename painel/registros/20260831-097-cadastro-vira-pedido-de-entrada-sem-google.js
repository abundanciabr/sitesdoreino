(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-097-cadastro-vira-pedido-de-entrada-sem-google",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A página de cadastro virou o pedido de vaga da escola, para quem não tem conta do Google",
  detalhe: "Você pediu: uma escola tem aluno ou não tem, não é site de notícias com 'deixe seu e-mail para acompanhar as novidades'. Foi isso que a página meshcraft.top/cadastro fazia até hoje: um formulário de captura de contato, sem ligação nenhuma com a lista de alunos.\n\nA PARTIR DESTE PR, quem preenche o formulário (nome, e-mail, WhatsApp, agora obrigatório) entra DIRETO na mesma fila 'Aguardando aprovação' que você já vê e decide em meshcraft.top/admin/escola/alunos/ — a mesma porta que o cadastro à mão do admin já usa. Três casos tratados na tela: pedido recebido (aguardando você), e-mail que já é aluno (mensagem própria, sem fingir que é um cadastro novo), e falha de rede (a página avisa e guarda o que a pessoa digitou). A página de cadastro e a de login também ganharam um link uma para a outra, para quem chega na porta errada.\n\nNÃO PRECISOU DE NENHUM PASSO SEU NA VPS: a ligação entre a página e a lista de alunos já existia desde 28/08 (para a home saber quem é aluno) e já dava conta da escrita nova, sem segredo novo para gerar.\n\nO QUE FICA PENDENTE, e é uma decisão sua, não um defeito: hoje a ÚNICA forma de alguém entrar no site depois de aprovado é o Google (decisão de 25/08). Uma pessoa sem Google pode se cadastrar e ser aprovada por este caminho novo, mas ainda não tem como logar no site sozinha depois — isso pede um projeto à parte (outra forma de entrar), e não estava no pedido de hoje.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/771",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null
});})();
