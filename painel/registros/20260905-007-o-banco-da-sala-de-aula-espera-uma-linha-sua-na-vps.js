(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-007-o-banco-da-sala-de-aula-espera-uma-linha-sua-na-vps",
  tipo: "pendencia",
  quando: "2026-09-05",
  titulo: "O banco da sala de aula (cursos) espera UMA linha sua na máquina (PR #1050)",
  detalhe: "O roteiro está pronto e testado (degrau 1.6 da célula cursos, TAR-148). "
    + "Quando o robô da maestro avisar que a sala de aula está pronta para "
    + "entrar no ar, cole esta linha DENTRO da máquina (a janela onde o texto "
    + "começa com deploy@srv ou root@srv, nunca a do seu computador):\n\n"
    + "curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-cursos.sh -o /tmp/c.sh && bash /tmp/c.sh meshcraft.top\n\n"
    + "Ele cria o banco da sala de aula e abre a conversa dela com o login e "
    + "com a lista de alunos. Se algo estiver estranho ele PARA sozinho e "
    + "escreve 'PAROU POR SEGURANÇA', sem ter criado nada. No fim, copie a "
    + "tela inteira e me mande. É seguro repetir.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1050",
  verificado_em: "2026-09-05",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A sala de aula fica pronta no código e nunca abre para os alunos: sem o banco, o programa dela reiniciaria sem parar.",
  recomendacao: "Rodar quando a maestro entregar a linha, com a máquina aberta. Leva menos de um minuto.",
  reversivel: true,
  impacto: "medio"
});})();
