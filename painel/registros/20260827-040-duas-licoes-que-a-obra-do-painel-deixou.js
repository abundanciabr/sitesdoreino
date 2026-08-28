(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-040-duas-licoes-que-a-obra-do-painel-deixou",
  tipo: "nota",
  quando: "2026-08-27",
  titulo: "Duas armadilhas novas no catalogo, das que so aparecem em producao",
  detalhe: "Toda obra aqui termina com o que ela ensinou entrando no catalogo de armadilhas — e a do painel deixou duas.\n\nA PRIMEIRA e a mais perigosa. Ao escrever a explicacao dentro do arquivo do painel, usei a palavra 'script' entre os sinais de menor e maior, num comentario. O servidor calcula uma assinatura de seguranca procurando exatamente esse padrao no arquivo, e nao sabe distinguir comentario de codigo: ele teria assinado o meu comentario e deixado o codigo de verdade sem assinatura. A pagina abriria em branco NO SITE e funcionaria perfeitamente no meu computador. Peguei antes de mergear, mas a suite estava toda verde — nenhum teste veria isso, porque a assinatura so existe quando o servidor responde. O detalhe cruel: o comentario existe justamente para explicar o codigo logo abaixo, entao quanto melhor a documentacao, maior a chance do defeito.\n\nA SEGUNDA custou um susto. Ao pedir o merge, o portao acusou 31 trabalhos que 'ninguem tinha contado a voce'. Fui conferir e os registros citavam quase todos. O portao nao errou: eu tinha chamado a ferramenta apontando para a pasta principal do projeto em vez da minha copia de trabalho — e ela mede a copia de onde ela e lida, nao aquela onde voce esta. A pasta principal esta 152 mudancas atrasada, entao ela mediu um livro velho. A divida de verdade era de dois trabalhos, e eu paguei os dois. Ja existia uma armadilha vizinha sobre isso (a 140, de outra sessao hoje), mas com outro gatilho: la o comando roda DE uma copia velha; aqui eu estava na copia certa e mesmo assim medi a errada. Nao editei a entrada dela — escrevi a minha ao lado e apontei para ela, que e a regra da casa.\n\nPOR QUE ISSO IMPORTA PARA VOCE: as duas sao da mesma familia — defeitos que a maquina de conferencia NAO ve, porque so existem quando o site responde de verdade. Sao exatamente o tipo de coisa que faz um robo dizer 'esta tudo verde' com o site quebrado. Cada uma dessas anotacoes e um dia que o proximo robo nao vai perder.",
  autoridade: "sessao",
  evidencia: "armadilhas/146-a-palavra-script-num-comentario-html-quebra-o-csp.md e armadilhas/147-o-caminho-do-script-escolhe-qual-repo-e-medido.md, indice regenerado por ci/indice_de_armadilhas.py (136 entradas). A primeira foi medida contando as ilhas de script com a MESMA regex de services/admin/apps/core/painel.py antes e depois do conserto; a segunda foi medida comparando a divida acusada rodando do clone principal (31) contra a real, rodando do worktree (2 — PRs 312 e 314, pagos no registro 20260827-038).",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
