(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-008-um-mapa-do-projeto-inteiro-para-outras-ias-lerem",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Criei um mapa completo do projeto para outras IAs lerem e sugerirem melhorias",
  detalhe: "Você pediu uma versão do nosso painel específica para outras IAs lerem — com tudo sobre a infraestrutura, arquitetura e ferramentas do projeto, menos o que elas não podem ter acesso — para que qualquer IA consiga vasculhar o projeto inteiro, do começo ao fim, e sugerir melhorias.\n\nO QUE CONSTRUÍ: uma pasta nova, painel/ia/, com um índice e sete documentos, um para cada parte do projeto — as leis e ritos que os robôs seguem, os erros que já aconteceram e os padrões por trás deles, o próprio mecanismo deste painel, as 12 peças (\"células\") que formam o site e como elas conversam entre si, a infraestrutura e os robôs de CI que testam e publicam tudo, as decisões de produto já tomadas e por quê, e por fim uma lista do que já sabemos que está pendente ou pode melhorar — para a IA não perder tempo redescobrindo o que este projeto já decidiu. Para escrever isso com informação real, mandei seis pesquisas em paralelo lendo o projeto inteiro (mais de 5.000 arquivos) antes de escrever a primeira linha; uma delas até corrigiu um número que eu tinha assumido errado (achei que só 8 das 12 células tinham 'constituição' própria — na verdade são as 12).\n\nO QUE FICOU DE FORA, DE PROPÓSITO: nenhum endereço de servidor, nenhuma senha, nenhum token — conferi isso com uma varredura dedicada antes de publicar, e de novo com uma checagem minha por cima. Uma IA que ler este mapa entende o projeto inteiro sem conseguir, por exemplo, entrar nos seus sistemas.\n\nUMA TRAVA NOVA: se um dia nascer uma célula nova (uma peça nova do site) e ninguém lembrar de atualizar o mapa, o robô de testes agora recusa até alguém corrigir — o mapa não pode ficar cego a uma célula nova em silêncio.\n\nDE QUEBRA, dois achados pequenos que documentei em vez de deixar passar: o CLAUDE.md não avisava que mexer no painel também acorda o deploy da área administrativa (corrigi a frase); e um teste de CI que reprova só em computador Windows, sem relação nenhuma com meu trabalho — confirmei isso comparando com uma cópia limpa do projeto antes de registrar, e de fato ele passou limpo na esteira real do GitHub (Linux) agora há pouco.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/266 MERGED (commit f71b5e40942d); checks muralhas/ci-celula/ci-celula-gate verdes; deploy https://github.com/abundanciabr/sitesdoreino/actions/runs/33079946402 (deploy-celula, célula admin) conclusion=success — build, push e ativação na VPS OK",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
