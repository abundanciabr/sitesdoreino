(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-052-um-passo-seu-na-vps-criar-o-banco-da-medicao",
  tipo: "pendencia",
  quando: "2026-09-04",
  titulo: "Um passo seu no servidor: criar o banco da parte que guarda a história dos números",
  detalhe: "É o PR #989. A parte nova (a que guarda a história dos números para o "
    + "painel poder dizer o que mudou) precisa do banco de dados dela, e criar "
    + "banco no servidor é passo que só você pode dar: nenhum robô tem acesso "
    + "lá (é a lei da casa desde o começo). Deixei pronto um comando de UMA "
    + "linha, que se recusa a agir se algo estiver estranho. Cole na janela do "
    + "servidor (aquela em que a linha começa com deploy@srv ou root@srv, "
    + "nunca a do seu computador):\n\n"
    + "curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-metricas.sh -o /tmp/m.sh && bash /tmp/m.sh\n\n"
    + "Ele mostra o que vai fazer, cria o banco, escreve a configuração e "
    + "termina dizendo PRONTO. Se algo estiver fora do lugar, ele para sozinho "
    + "com uma mensagem começando por PAROU POR SEGURANÇA, sem ter mexido em "
    + "nada. Me mande a última tela. Enquanto isso não acontece, a parte nova "
    + "existe no código, é testada, mas não está ligada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/989",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "A parte que guarda a história dos números fica desligada, e o painel continua só sabendo dizer como as coisas estão agora, nunca o que mudou. Os acontecimentos do site vão passando sem ser guardados.",
  recomendacao: "Rodar quando puder: leva menos de um minuto e não derruba nada do que está no ar.",
  reversivel: true,
  impacto: "medio"
});})();
