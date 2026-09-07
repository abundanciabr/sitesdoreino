(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-074-a-chave-da-ia-avisa-se-nao-chegou",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "O comando da chave da IA avisa quando falha",
  detalhe: "A tela dizia que deu certo mesmo quando a chave nao chegava no container. Agora sao tres finais: PRONTO, aviso de nada a recarregar, e PAROU POR SEGURANCA.\n\nCole na janela da VPS (comeca com deploy@srv, nunca PS C:\>). Fica um minuto calado:\n\ncd /opt/plataforma && curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/por-a-chave-da-ia-do-admin.sh -o /tmp/ia-admin.sh && bash /tmp/ia-admin.sh\n\nO 068 escreveu esse aviso com uma barra a menos.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1338",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: "20260907-068-falta-um-comando-seu-para-o-robo-analista",
  gravidade: "ambar",
  se_eu_nao_decidir: "o robo analista do painel segue mudo"
});})();
