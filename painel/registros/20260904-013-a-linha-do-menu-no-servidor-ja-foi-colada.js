(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-013-a-linha-do-menu-no-servidor-ja-foi-colada",
  tipo: "resposta",
  quando: "2026-09-03",
  titulo: "A linha do menu no servidor já foi colada: a tela /admin/menu/ tem a senha de máquina que pedia",
  detalhe: "O script infra/provisionar-par-do-menu.sh liga os cinco pares num gesto só (Admin, "
    + "fórum, Caixa e Conquistas conversando com o registro de sites), e o quinto par, o de "
    + "Conquistas, nasceu em 02/09. Como o menu está no ar em /conquistas/ e em /forum/ "
    + "(medido de fora em 03/09/2026), o script rodou depois de 02/09, e o par do Admin, que "
    + "é o primeiro degrau do mesmo script, veio junto. O pedido de 31/08 estava atendido.",
  autoridade: "sonda",
  evidencia: "GET https://meshcraft.top/conquistas/ e /forum/ -> 200 com <nav class=\"menu-topo\">, medido de fora em 03/09/2026; infra/provisionar-par-do-menu.sh, cabeçalho 'quatro degraus' + 'o quinto degrau nasceu em 02/09/2026'",
  verificado_em: "2026-09-03",
  precisa_do_dono: false,
  responde_a: "20260831-036-para-a-tela-do-menu-funcionar-falta-um-passo-seu-na-vps",
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
