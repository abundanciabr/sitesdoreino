(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-068-as-regras-dos-robos-ficaram-tres-vezes-mais-curtas",
  tipo: "decisao",
  quando: "2026-09-06",
  titulo: "As regras dos robôs ficaram três vezes mais curtas, e a história delas mudou de casa",
  detalhe: "O arquivo de regras que todo robô relê a cada passo tinha 60 mil caracteres, e quase metade era história: a data em que cada regra nasceu, o que custou, qual pedido a motivou. Você mediu o preço disso: 421 milhões de tokens em 4 dias só para reler o mesmo texto.\n\nDecisão sua, de hoje: o arquivo carrega só a regra, o comando e quem a faz cumprir. A história inteira foi para um documento de memória, que se abre quando alguém precisa do motivo e custa zero o resto do tempo. As onze regras do Padrão de Trabalho continuam lá, palavra por palavra.\n\nPara não reengordar em silêncio, o arquivo ganhou um teto de tamanho que a integração confere em todo PR. Subir o teto é decisão sua.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1215 (PR #1215): 60.005 para 19.627 caracteres (32,7%). python ci/padrao_de_trabalho.py: PASS 6/6, teto 20.000. python ci/leis_sem_mecanismo.py: PASS. pytest: 52 passed. python ci/ci.py --apenas muralhas: PASS 13/13.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
