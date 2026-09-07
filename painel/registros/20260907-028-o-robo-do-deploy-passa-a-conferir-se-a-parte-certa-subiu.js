(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-028-o-robo-do-deploy-passa-a-conferir-se-a-parte-certa-subiu",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "O robo do deploy passa a conferir se a parte certa do site subiu",
  detalhe: "O site sobe em partes separadas. O robo que conserta publicacao perdida so olhava se a versao nova do codigo tinha chegado, e dava a coisa por resolvida. Em 05/09 isso escondeu uma entrega: a versao chegou, a parte dela nunca subiu, e tres telas verdes disseram que estava tudo certo.\n\nAgora ele confere parte por parte, e so encerra quando cada uma subiu de verdade. Faltando uma, repete e diz qual e.\n\nProvado com o caso de 05/09: o robo antigo dizia 'nao precisa repetir'; o novo aponta a parte em falta.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1287",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
