// Ultimo fecho da auditoria das Ondas 3 a 6: o mantenedor mandou consertar
// tambem o roteamento por prosa da esteira (PR #493), e as duas licoes do
// dia foram para armadilhas/174 e 175 (PR #490).
(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-031-a-esteira-parou-de-decidir-por-uma-frase-com-acento",
  tipo: "entrega",
  quando: "2026-08-29",
  titulo: "A esteira parou de decidir por uma frase com acento — e as duas lições do dia entraram no livro de armadilhas",
  detalhe: "Você mandou consertar a última coisa que a auditoria viu e não tinha consertado: a esteira de pouso decidia o destino de um pedido PROCURANDO UMA FRASE EM PORTUGUÊS, com acento, dentro do relatório do portão. Feito, e junto foram para o livro as duas lições do dia.\n\nO QUE ERA (pedido 493)\n\nQuando o portão reprovava um pedido só porque a base tinha envelhecido, ele escrevia isso numa frase para gente ler. A esteira procurava essa frase para saber o que fazer. Funcionava — e era frágil por três motivos que não se anunciam: a frase é texto para humano, e melhorar a redação numa manhã quebraria o roteamento à tarde; o acento atravessa quatro camadas de programa até chegar na busca, e já houve dois casos aqui de acento se corrompendo no caminho; e o erro, se acontecesse, seria do pior tipo — a esteira trataria 'só precisa atualizar' como 'reprovou', tiraria a etiqueta e comentaria 'não pousei' num pedido que estava perfeito.\n\nAchei por acidente, e essa é a melhor parte: um teste meu escreveu a frase sem acento e o roteamento errou exatamente assim, na minha frente.\n\nO QUE É AGORA\n\nO portão passou a escrever também um código curto e sem acento nenhum, e é o código que a esteira lê. A frase em português continua lá, para você e para mim — ela só deixou de decidir. Dois guardas novos leem os DOIS arquivos e comparam: se alguém mudar o código num lado e esquecer o outro, fica vermelho antes de a esteira errar de verdade.\n\nA prova que mais me convenceu: fiz o teste entregar a frase SEM ACENTO de propósito, e o roteamento continuou certo. Antes, isso quebrava.\n\nAS DUAS LIÇÕES DO DIA FORAM PARA O LIVRO DE ARMADILHAS (pedido 490)\n\nA primeira é a causa-raiz do buraco dos testes: a ferramenta que lista o que um pedido mudou mostra só o DESTINO quando um arquivo é renomeado — nunca de onde ele veio. Por isso um renomear de uma linha tirou 17 testes da suíte com o portão dizendo 'nada sumiu'. A entrada tem a cura e aponta os outros lugares deste projeto que leem a mesma coisa e merecem conferência.\n\nA segunda é sobre mim: hoje eu quase te disse que a linha principal do projeto tinha regredido e levado o trabalho do dia junto. Não tinha — eu li uma comparação ao contrário, e o título do commit no topo carregava o número de um pedido antigo que só tinha pousado à tarde. Medi de novo pelo outro lado e desfiz a conclusão antes de te falar. A lição ficou escrita: antes de te dar um susto, medir duas vezes. Você é leigo e não tem como conferir sozinho — você acreditaria em mim, e um susto falso gasta a confiança de que o susto verdadeiro vai precisar.",
  autoridade: "github",
  evidencia: "PRs #490 (armadilhas 174 e 175) e #493 (o motivo vira codigo), ambos MERGED, conferidos por gh pr view --json state,mergeCommit: 35603549f83d e f1ef1d51. Prova de que o roteamento nao depende mais do acento: com o duble entregando a frase SEM acento e so o codigo intacto, os 4 guardas da fila da pista continuam verdes; antes o mesmo cenario reprovava. Prova por mutacao: a pista voltar a rotear pela frase, ou o token mudar so no portao, deixa 1 guarda vermelho em cada caso. test_mergear.py 88 -> 93 verdes. E o run 33269335742 da esteira, o primeiro depois do merge, mostra o grep novo (MOTIVO-DA-RECUSA) e terminou success. Nenhum dos dois PRs toca services/ ou painel/, entao nao houve publicacao a conferir.",
  verificado_em: "2026-08-29",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
