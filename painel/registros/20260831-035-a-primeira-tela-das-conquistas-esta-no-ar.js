(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-035-a-primeira-tela-das-conquistas-esta-no-ar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "A primeira tela das conquistas esta no ar, e o aluno ja abre a pagina dele",
  detalhe: "De manha a parte que guarda o progresso do aluno estava fora do ar. Agora ela tem endereco, tem pagina e tem aparencia: quem entrar em meshcraft.top/conquistas ve uma tela de verdade.\n\nO QUE ELA MOSTRA HOJE: para quem esta logado, o degrau em que esta, o titulo que ganhou e uma barra com quanto falta para o proximo. Para quem nao entrou, a mesma pagina com um convite para entrar, nunca um erro. Essa escolha foi deliberada: uma pagina que recusa quem ainda vai se matricular perde a pessoa exatamente no momento em que ela estava curiosa.\n\nO PERFIL NASCE SOZINHO na primeira visita, zerado. Nao existe tela de 'voce ainda nao tem perfil': entrar hoje e nao ter feito nada ainda e a verdade sobre todo aluno no primeiro dia, e a pagina trata isso como um estado normal, nao como um erro.\n\nUMA REGRA DE VISUAL QUE VEIO DA SUA LEI: o numero de experiencia e a MENOR coisa da pagina. Quem ocupa o topo e o titulo do degrau, que fala de quem a pessoa esta virando. A lei escreve isso com todas as letras, 'XP nunca maior que a imagem da obra', e o arquivo de estilo carrega esse motivo escrito para quem for mexer nele um dia.\n\nDUAS ARMADILHAS ANTIGAS DA CASA NAO PEGARAM, e nao foi sorte: a pagina tem rota propria para servir o proprio estilo, e o endereco desse estilo e montado de um jeito que carrega o prefixo /conquistas junto. Sem essas duas coisas a tela abriria sem formatacao nenhuma em producao, e SO em producao, funcionando perfeitamente na maquina de quem programou.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/708 (TAR-074) mergeado, commit 5ab960ae; deploy-celula run 33412064640 completed/success, lido por gh run view --json. PROVA DE FORA em 31/08/2026: https://meshcraft.top/conquistas/ 404 antes -> 200 depois, com <title>Conquistas | Meshcraft Academy</title> e o texto 'Suas conquistas ficam aqui'; https://meshcraft.top/conquistas/static/gamificacao.css responde 200. 107 testes verdes na celula (11 novos), black limpo, contrato conferido e identico ao congelado (263 linhas), 13 muralhas PASS.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
