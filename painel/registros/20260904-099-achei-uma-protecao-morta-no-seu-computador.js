(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-099-achei-uma-protecao-morta-no-seu-computador",
  tipo: "nota",
  quando: "2026-09-04",
  titulo: "Um alarme falso na fábrica: dois testes acusavam um defeito que não existe",
  detalhe: "Dois testes da fábrica ficam vermelhos no seu computador e verdes no "
    + "servidor, e eu quase reportei que uma proteção do robô estava quebrada. Fui "
    + "medir de novo e era o contrário: a proteção funciona (ela disparou ao vivo "
    + "num trabalho hoje), e quem está errado é o teste, que imita o robô de um jeito "
    + "que o robô de verdade não é. Nada está fora do ar e nada se perdeu. O custo é "
    + "um alarme falso que faz um robô perder tempo investigando. Deixei na fila como "
    + "TAR-142, com as duas medições, a errada e a certa.",
  autoridade: "sessao",
  evidencia: "PR #1033. A remedição disparou ao vivo no PR #1033 ('remeço em 20s'), "
    + "e ci/mergear.py chama configurar_saida(); o dublê do teste, não.",
  verificado_em: "2026-09-04",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
