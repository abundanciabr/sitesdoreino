(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-017-a-licao-do-roteador-sem-cadeado-nao-estava-contada",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "A licao do endereco que ficou invisivel entrou no projeto e nao estava contada no livro",
  detalhe: "ESTA LINHA E DE CONTABILIDADE — o acontecimento ja esta contado, faltava so o numero.\n\nO QUE ACONTECEU (PR #563, mergeado na madrugada de 30/08): outro robo escreveu a licao de um defeito real do dia — um endereco do site que ficou INVISIVEL por causa de uma linha faltando na configuracao do porteiro, com a entrega aparecendo verde duas vezes seguidas. O YAML era valido, os programas estavam de pe, tudo dizia 'certo' — e o endereco nao existia.\n\nA LICAO MAIOR, que vale alem do caso: um conferente que so olha se a configuracao esta bem escrita tem esse ponto cego. So medir o que o mundo recebe de fora pega esse tipo de defeito.\n\nO QUE FALTAVA: aquele PR levava DOIS registros dentro dele, contando a entrega e o incidente — mas os dois citam os numeros #544, #550 e #560, e nenhum cita o #563, o proprio PR que os carregou. E o ciclo natural: quando se escreve o registro, o numero do PR ainda nao existe. O conferente de contas cobra pelo NUMERO citado, entao o #563 ficava marcado como 'entrou e ninguem contou', e a porta de entrega travava para todas as sessoes seguintes.\n\nE a armadilha 185 em pessoa, pela terceira vez. Para ler o que de fato aconteceu, os registros sao o 125 e o 126 de 29/08.",
  autoridade: "sessao",
  evidencia: "PR #563 (https://github.com/abundanciabr/sitesdoreino/pull/563), 'armadilhas: roteador do Traefik sem tls fica invisivel com o deploy verde (187)', mergeado em 2026-08-30T01:57:11Z por abundanciabr. MEDIDO: `python ci/mergear.py 569 --conferir` acusava esse merge como divida. CAUSA CONFERIDA: `grep -o 'pull/[0-9]*|#[0-9]*'` nos dois registros que o PR carregava (20260829-125 e 20260829-126) devolve #544, #550 e #560 - o numero 563 nao aparece em nenhum dos dois. E exatamente a armadilhas/185. Este registro vai SOZINHO num PR so de painel/, porque a pista julga a divida lendo a main e nao o PR (armadilhas/190, escrita nesta mesma sessao).",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
