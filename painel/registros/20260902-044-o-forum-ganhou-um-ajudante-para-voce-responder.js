(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260902-044-o-forum-ganhou-um-ajudante-para-voce-responder",
  tipo: "entrega",
  quando: "2026-09-02",
  titulo: "O forum ganhou um ajudante: voce clica, a IA escreve o rascunho, voce publica",
  detalhe: "Voce pediu um agente de IA para responder no forum, so para o Admin. Esta pronto, e do jeito que voce descreveu.\n\nNA TELA: dentro de uma conversa, logo acima da caixa de responder, aparece 'Rascunhar com a IA', com um campo opcional de uma linha para voce dizer COMO ela deve responder ('responda curto', 'fale da aula 3') e um botao 'Gerar resposta'. So voce e os professores enxergam; para o aluno nem o endereco existe.\n\nA DECISAO QUE MAIS IMPORTA: A IA NUNCA PUBLICA. O texto cai dentro da caixa de resposta e fica ali ate voce clicar em Responder, e sai com o SEU nome.\n\nO QUE NAO SAI DAQUI: o nome e o e-mail de quem perguntou (a conversa viaja rotulada 'Aluno' e 'Escola') e mensagem que voce ja tinha tirado do ar.\n\nO QUE ELA FOI PROIBIDA DE FAZER: inventar preco, prazo, turma, reembolso ou conteudo de aula. Nesses casos responde a parte tecnica e diz que a escola confirma o resto. Tambem foi proibida de usar travessao e, se escapar um, a tela AVISA antes de voce publicar.\n\nFALTA UM PASSO SEU: criar a chave da Anthropic. Ate la a caixa avisa que a IA nao esta ligada, o forum funciona como hoje e nada e cobrado.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/875. Suite forum 264 passed (24 novos); ci/tests 1499 passed. Prova vermelho->verde por sabotagem (armadilhas/195): nome do aluno viajando, a view publicando sozinha, travessoes_em cego e mensagem removida viajando, cada uma derrubando o teste que a vigia. Muralhas locais PASS, black limpo. Armadilha nova 288. Toca infra/ (CODEOWNERS).",
  verificado_em: "2026-09-02",
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
