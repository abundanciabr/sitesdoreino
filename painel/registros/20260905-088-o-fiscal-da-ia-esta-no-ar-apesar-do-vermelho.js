(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-088-o-fiscal-da-ia-esta-no-ar-apesar-do-vermelho",
  tipo: "nota",
  quando: "2026-09-05",
  titulo: "O fiscal da IA ficou vermelho na publicacao, e mesmo assim esta no ar",
  detalhe: "A publicacao do PR #1124 falhou duas vezes, e nas duas o motivo foi o mesmo: o robo que publica nao conseguiu abrir a porta da sua maquina. Nao foi defeito do codigo.\n\nO IMPORTANTE, e por isso este registro existe: o codigo JA ESTA NO AR. Uma publicacao verde posterior levou o mesmo commit junto, e a vacina da casa conferiu isso sozinha em vez de repetir. Repetir agora publicaria um mundo mais velho, que seria um retrocesso silencioso.\n\nConferido de fora depois de tudo: o curso responde na internet e a fila de revisao continua fechada para quem nao esta na lista, que e o desenho.",
  autoridade: "github",
  evidencia: "python ci/rerun_de_deploy.py --run 33995099105 -> 'timeout-ssh=True porta22=True site=200' e 'NADA: a ultima publicacao verde (ad8205b076da) ja contem 82a4f1edad24'. De fora: /cursos/healthz 200, /cursos/ 200, /cursos/plantao 403. Armadilhas 127 e 231.",
  verificado_em: "2026-09-05",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
