(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-046-o-banco-das-encomendas-espera-uma-linha-sua-na-vps",
  tipo: "pendencia",
  quando: "2026-09-04",
  titulo: "O banco das Encomendas espera UMA linha sua na máquina (PR #982)",
  detalhe: "O roteiro está pronto e testado. Quando você puder, cole esta linha "
    + "DENTRO da máquina (a janela onde o texto começa com deploy@srv ou "
    + "root@srv, nunca a do seu computador):\n\n"
    + "curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-encomendas.sh -o /tmp/e.sh && bash /tmp/e.sh meshcraft.top\n\n"
    + "Ele cria o banco da área de encomendas e abre a conversa dela com o "
    + "login e com a lista de alunos. Se algo estiver estranho ele PARA sozinho "
    + "e escreve 'PAROU POR SEGURANÇA', sem ter criado nada. No fim, copie a "
    + "tela inteira e me mande.\n\n"
    + "Sem esse passo a área não pode entrar no ar: o programa dela reiniciaria "
    + "sem parar procurando um banco que não existe.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/982",
  verificado_em: "2026-09-04",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A área de encomendas fica pronta no código e nunca abre para os alunos.",
  recomendacao: "Rodar quando você tiver a máquina aberta. Leva menos de um minuto e é seguro repetir.",
  reversivel: true,
  impacto: "medio"
});})();
