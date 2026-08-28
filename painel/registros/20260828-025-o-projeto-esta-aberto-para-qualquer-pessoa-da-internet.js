(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-025-o-projeto-esta-aberto-para-qualquer-pessoa-da-internet",
  tipo: "incidente",
  quando: "2026-08-28",
  titulo: "O projeto está aberto para qualquer pessoa da internet ler — isso pode ser proposital, mas precisa ser escolha sua",
  detalhe: "Enquanto conferia os conselhos das IAs, descobri que o repositório do projeto está PÚBLICO no GitHub. Qualquer pessoa na internet consegue ler o código inteiro, este livro de ocorrências, as decisões de negócio e os planos. Não é preciso senha nem convite.\n\nIsso pode ter sido escolha sua, e tem lados bons de verdade: é justamente por ser público que o projeto tem de graça a proteção da versão oficial e as máquinas que rodam os testes, que em projeto fechado seriam pagas. Parte do plano novo se apoia nisso.\n\nMas tem o outro lado, e é por isso que virou registro: o que está escrito aqui fica visível para sempre para qualquer um, inclusive concorrentes. E o aviso automático do GitHub para senha vazada por acidente — que é gratuito justamente em projeto aberto — está DESLIGADO. Conferi a lista de arquivos e não encontrei senha nenhuma guardada; só arquivos de exemplo. Mas isso foi uma olhada, não uma auditoria.\n\nO segundo ponto do mesmo assunto: a pasta do projeto mora dentro do OneDrive. Duas das cinco IAs apontaram isso sozinhas, sem combinar, como causa de estrago silencioso: o OneDrive copia arquivos enquanto o controle de versão está escrevendo neles, e com vários robôs trabalhando ao mesmo tempo isso corrompe a pasta sem avisar. Nenhuma delas sabia da outra quando escreveu.\n\nNão mexi em nada. As duas coisas são decisão sua.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/362",
  verificado_em: "2026-08-28",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: "O projeto segue visível para qualquer pessoa, e sem o aviso automático que avisaria se um robô publicasse uma senha por acidente. E a pasta continua num lugar onde o OneDrive pode corromper o histórico com vários robôs trabalhando ao mesmo tempo — o tipo de estrago que só aparece quando já é tarde.",
  recomendacao: "Sobre ser público: se foi proposital, ligue o aviso de senha vazada e siga — é grátis e leva um minuto. Se não foi, dá para fechar, mas aí o projeto perde a proteção da versão oficial e as máquinas de teste gratuitas, e parte do plano precisa ser refeita. Sobre o OneDrive: mover a pasta para fora é a recomendação, e é trabalho que eu faço com você acompanhando.",
  reversivel: true,
  impacto: "alto"
});})();
