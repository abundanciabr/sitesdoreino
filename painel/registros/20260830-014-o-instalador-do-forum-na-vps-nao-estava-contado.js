(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-014-o-instalador-do-forum-na-vps-nao-estava-contado",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "O instalador do forum na VPS entrou no projeto e nao estava contado no livro",
  detalhe: "ESTA LINHA E DE CONTABILIDADE, e vale dizer isso na cara: o acontecimento e de outra sessao, e o que faltava era o registro dele no livro.\n\nO QUE ACONTECEU (PR #547, mergeado na madrugada de 30/08): o instalador do forum na VPS existia desde 28/08 numa bancada abandonada, com 290 linhas que nunca tinham sido guardadas. Nao havia nada equivalente no projeto — 9 celulas irmas tinham o seu, o forum nao. Sem esse instalador, o passo que so voce pode dar na VPS simplesmente nao existe, e o forum subiria sem banco.\n\nE A CONFERENCIA ACHOU UM FURO ANTES DE DOER: o script escrevia a senha de acesso do forum nos arquivos de configuracao das celulas 'identidade' e 'alunos', mas nao mandava essas duas relerem a configuracao. Um programa so le a configuracao dele quando renasce — as duas seguiriam sem conhecer o forum, e o forum subiria dando 'acesso negado' em toda pagina, COM a entrega aparecendo verde. Foi corrigido no mesmo PR.\n\nPOR QUE ESTE REGISTRO EXISTE: o conferente de contas do projeto cobra pelo NUMERO do PR citado, e o #547 nao aparecia em registro nenhum — entao ele ficava marcado como 'entrou e ninguem contou ao dono', e a porta de entrega travava para todas as sessoes seguintes. E a armadilha 185 cobrando pela segunda vez. Para ler o que de fato foi feito, o lugar e o proprio PR #547.",
  autoridade: "sessao",
  evidencia: "PR #547 (https://github.com/abundanciabr/sitesdoreino/pull/547), 'infra: o instalador do forum na VPS - resgatado de uma bancada orfa, conferido e corrigido', mergeado em 2026-08-30T00:57:18Z por abundanciabr, tocando infra/provisionar-forum.sh, infra/env/forum.env.exemplo e ci/tests/test_provisionamento_nao_perde_variavel.py. MEDIDO: `python ci/mergear.py 566 --conferir` acusava esse merge como divida do livro porque nenhum registro citava o numero 547. Conferido lendo o proprio PR com `gh pr view 547 --json title,mergedAt,mergedBy,files,body`.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null
});})();
