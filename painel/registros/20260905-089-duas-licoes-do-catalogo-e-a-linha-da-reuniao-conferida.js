(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-089-duas-licoes-do-catalogo-e-a-linha-da-reuniao-conferida",
  tipo: "entrega",
  quando: "2026-09-05",
  titulo: "Duas licoes que dois despachos de hoje nao couberam no orcamento entraram no catalogo",
  detalhe: "O PR #1114 (metricas) e o PR #1115 (admin) esbarraram no orcamento de 15 arquivos e reportaram a licao em texto em vez de espremer arquivo, como manda a regra. Este PR paga as duas: armadilhas/351 (sabotagem em campo extra do dicionario de retorno nao prova nada quando a rota tem response=Schema declarado - a mutacao tem de mudar o Schema) e armadilhas/352 (o pluralize do Django trata zero como plural, entao contagem com verbo conjugado sai torta - 0 envelheceuram, 3 eventos chegou - e so a previa renderizada pega isso).\n\nTambem foi conferida a terceira parte do brief: reescrever a linha de reuniao.html sobre o laboratorio, condicionada ao PR #1127 ja ter mergeado. Conferido duas vezes (gh pr view 1127) - ele continua OPEN, sem mergedAt, e a rota do laboratorio nao existe em origin/main. A linha continua verdadeira e nao foi tocada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1131 (PR #1131). python ci/indice_de_armadilhas.py -> PASS (327 entradas); suite da admin (python -m pytest -q, Postgres proprio isolado) -> 1117 passed antes e depois; python ci/travessao.py -> PASS (divida herdada estavel em 3); python ci/ci.py --apenas muralhas -> PASS nas 13 muralhas; gh pr view 1127 --json state,mergedAt -> OPEN/null nas duas conferencias.",
  verificado_em: "2026-09-05",
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
