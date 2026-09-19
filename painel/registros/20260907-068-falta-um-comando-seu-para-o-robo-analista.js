(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-068-falta-um-comando-seu-para-o-robo-analista",
  tipo: "pendencia",
  quando: "2026-09-07",
  titulo: "Falta um comando seu para o robo analista poder falar",
  detalhe: "Sem a chave da IA na area administrativa, o robo analista do painel nasce mudo. O roteiro que a leva ate la nao pede nada: ela ja esta na maquina.\n\nDEPOIS do merge, cole na janela da VPS (a que comeca com deploy@srv ou root@srv, nunca PS C:\>). Fica um minuto calado e no fim escreve PRONTO:\n\ncd /opt/plataforma && curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-admin.sh -o /tmp/ia-admin.sh && bash /tmp/ia-admin.sh",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1332",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "o robo analista segue mudo"
});})();
