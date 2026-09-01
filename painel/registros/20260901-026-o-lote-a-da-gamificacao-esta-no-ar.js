(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260901-026-o-lote-a-da-gamificacao-esta-no-ar",
  tipo: "entrega",
  quando: "2026-09-01",
  titulo: "As quatro bordas da gamificacao entraram, e as quatro subiram verdes",
  detalhe: "O Lote A do plano dos lotes da gamificacao fechou: quatro robos em paralelo, quatro celulas diferentes, quatro PRs, nenhum revertido.\n\nO que entrou, em uma linha cada:\n\nA medalha de Fundador para quem ja estava aqui (PR 826, celula gamificacao). A medalha existia no banco desde 30/08, com nome e descricao prontos, e nao havia caminho nenhum para entrega-la a ninguem. Agora ha um comando re-executavel.\n\nAs frases dos quatro avisos da gamificacao no sininho (PR 827, celula sugestoes). Ate hoje a carta de subida de nivel chegava e caia no cartao generico de \"este recado e de um tipo que esta tela ainda nao sabe mostrar\".\n\nA etiqueta de nivel ao lado de quem escreve no forum (PR 828, celula forum). O forum e o lugar com mais gente passando, e o progresso do aluno so existia para quem procurava a pagina de conquistas.\n\nO quadrinho de progresso na home de quem entrou (PR 829, celula funil). E a primeira tela depois do login.\n\nOs quatro deploys terminaram em success, lidos um a um por gh run view --json: 33526679768, 33527589011, 33528867838 e 33528181141.\n\nPROVA DE FORA, na internet publica, depois dos quatro deploys: a home responde 200 e ja serve a folha nova do quadrinho; o forum responde 200 e a folha dele ja traz a regra da etiqueta de nivel; a pagina de conquistas responde 200; a folha da Caixa ja traz a classe da carta de celebracao e a porta dela continua devolvendo 302 para o login.\n\nE a parte que precisa ser dita com todas as letras, para ninguem achar que falhou: NENHUMA das duas telas novas mostra coisa alguma hoje, e isso e o comportamento certo. A etiqueta do forum depende de uma senha de maquina que so o mantenedor instala, e o quadrinho da home depende da outra. Alem disso a economia inteira continua desligada, entao nao existe progresso a mostrar. As duas telas falham para o lado de nao desenhar nada, em vez de quebrar: medido no ar, a etiqueta aparece zero vezes na pagina do topico e o quadrinho aparece zero vezes na home.\n\nTestes das quatro celulas somados: 1.491 antes, 1.620 depois.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/826",
  verificado_em: "2026-09-01",
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
