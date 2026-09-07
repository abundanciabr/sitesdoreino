(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-038-os-testes-do-robo-do-deploy-passam-a-medir-o-codigo",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "Os testes do robo do deploy passam a medir o codigo, e nao a si mesmos",
  detalhe: "O revisor automatico leu a entrega anterior na hora do merge e achou dois testes fracos: um conferia um valor que ele mesmo tinha escrito, e o outro so dizia que algo nao aconteceu, o que fica verde por qualquer motivo. Os dois foram refeitos, e entrou um terceiro que impede o robo de ficar repetindo publicacao para sempre.\n\nProva: arrancando a regra do codigo, caem exatamente os 6 testes que a protegem, cada um pelo nome. Nenhum outro respondeu no lugar deles.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1299",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: "20260907-028-o-robo-do-deploy-passa-a-conferir-se-a-parte-certa-subiu",
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
