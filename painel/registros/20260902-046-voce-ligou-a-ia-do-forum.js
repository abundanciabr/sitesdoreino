(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-046-voce-ligou-a-ia-do-forum",
  tipo: "resposta",
  quando: "2026-09-02",
  titulo: "Voce ligou a IA do forum: a chave esta no lugar",
  detalhe: "Voce criou a chave da Anthropic, pos o teto de gasto e rodou o script dentro da VPS. Ele terminou com PRONTO, e esse PRONTO nao e educado: ele so aparece quando o script vai conferir DENTRO do container do forum e encontra a chave com o tamanho certo. Se nao encontrasse, a mensagem seria outra.\n\nENTAO O QUE MUDA AGORA: a caixa 'Rascunhar com a IA' deixa de dizer que a IA nao esta ligada e passa a mostrar o botao 'Gerar resposta', com o campo opcional de orientacao. Quem enxerga continua sendo so voce e os professores.\n\nO QUE AINDA NAO FOI PROVADO, e vale dizer com todas as letras: eu conferi que a chave chegou ao lugar certo, nao que ela funciona. Chave valida, conta com credito e modelo respondendo so se provam gerando uma resposta de verdade. Assim que voce apertar o botao numa duvida e o texto aparecer, isso vira registro proprio.\n\nSE O BOTAO RECUSAR, ele nao quebra a tela: volta a mesma conversa com uma frase em portugues dizendo o que houve, e cada motivo tem a frase dele (chave recusada, conta no limite, demorou, nao respondeu). E as frases mandam para lugares diferentes de proposito.",
  autoridade: "mantenedor",
  evidencia: "O mantenedor rodou infra/por-a-chave-da-ia-do-forum.sh na VPS e relatou o == PRONTO ==, que o script so imprime depois de ler ANTHROPIC_API_KEY de dentro do container do forum e conferir o tamanho. Falta a prova de ponta a ponta (uma resposta gerada de verdade), e por isso este registro nao se declara verde.",
  verificado_em: null,
  precisa_do_dono: false,
  responde_a: "20260902-038-preciso-que-voce-crie-a-chave-da-ia-do-forum",
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
