(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-119-as-etapas-explicadas-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A Caixa já está explicando as etapas para os alunos, no ar",
  detalhe: "O PR 782 entrou na main e o deploy da Caixa ficou verde. A partir de agora, quem abre uma ideia lê o que a situação dela significa, e quem abre o quadro pode abrir a legenda das quatro etapas. A frase \"votar nunca fecha\" está lá também.\n\nO nome \"Em análise\" continua, como você decidiu. O que mudou não foi o rótulo: foi a Caixa deixar de mostrar quatro bolinhas sem dizer o que elas querem dizer.\n\nConferido de fora, no site de verdade, e não só nos testes: a folha de estilo publicada já traz as classes novas da legenda, e o quadro continua exigindo login antes de mostrar qualquer coisa (302 para a tela de entrar), que é como tem de ser.\n\nO caminho até aqui teve uma parada que vale registrar. O PR ficou vermelho por herança: o contrato da Caixa tinha ganhado uma promessa nova (corrigir o texto de uma ideia, PR 779) e o código que a cumpre ainda não tinha entrado. Nesse intervalo, qualquer PR que tocasse a Caixa herdava o vermelho. Medi isso numa cópia limpa da main, sem uma linha deste trabalho, para não afirmar por dedução. Esperei o PR 785 pousar, trouxe a main e ficou verde. Não contornei o portão: ele estava certo.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/782 MERGED, commit 8538296d. deploy-celula run 33446494887, sha 8538296db: status completed, conclusion success, lido por 'gh run view --json status,conclusion' e nao pelo exit de um pipe. PROVA DE FORA, no site publicado: https://meshcraft.top/forms/sugestoes/static/sugestoes/caixa.css devolve 8 ocorrencias das classes .legenda-item/.legenda-voto; https://meshcraft.top/forms/sugestoes/ devolve 302 para /forms/sugestoes/entrar. Antes do merge, na bancada: celula 562 passed, black limpo em 109 arquivos, freeze de contrato PASS (1062 linhas, 10 operacoes com autenticacao conferida na fonte), muralhas 13/13 PASS. O vermelho herdado foi medido em worktree limpo de origin/main: 'contrato/sugestoes FAIL' e 'POST /gestao/ideias/{sugestao_id}/texto congelado: exige credencial, codigo: <ausente>' sem uma linha deste PR.",
  verificado_em: "2026-08-31",
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
