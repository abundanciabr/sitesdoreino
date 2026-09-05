(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-026-as-conversas-da-sala-de-aula-esperam-uma-linha-sua-na-vps",
  tipo: "pendencia",
  quando: "2026-09-05",
  titulo: "As conversas da sala de aula esperam UMA linha sua na máquina, logo depois da linha do banco (PR #1066)",
  detalhe: "O roteiro que liga as quatro conversas da sala de aula (quem entrou, se a "
    + "pessoa tem matrícula, o menu do site, e o editor de aulas do Admin) está "
    + "pronto e testado (degrau 1.8b, TAR-162). Cole DENTRO da máquina (a janela "
    + "onde o texto começa com deploy@srv ou root@srv, nunca a do seu computador), "
    + "DEPOIS da linha do banco da sala de aula (o pedido 20260905-007):\n\n"
    + "curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-pares-da-sala-de-aula.sh -o /tmp/s.sh && bash /tmp/s.sh\n\n"
    + "Se a linha do banco ainda não tiver rodado, ele PARA sozinho, escreve "
    + "'PAROU POR SEGURANÇA' e mostra qual linha colar primeiro. Nenhum segredo "
    + "aparece na tela. No fim, copie a tela inteira e me mande. É seguro repetir.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1066",
  verificado_em: "2026-09-05",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: "A sala de aula abre tratando todo mundo como visitante e sem menu, e o editor de aulas do Admin não consegue gravar: nada quebra, mas nenhum aluno entra na aula.",
  recomendacao: "Rodar logo depois da linha do banco, na mesma sessão da máquina. Leva segundos.",
  reversivel: true,
  impacto: "medio"
});})();
