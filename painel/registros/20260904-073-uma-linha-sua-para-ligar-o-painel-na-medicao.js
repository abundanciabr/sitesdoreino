(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260904-073-uma-linha-sua-para-ligar-o-painel-na-medicao",
  tipo: "pendencia",
  quando: "2026-09-04",
  titulo: "Uma linha sua no servidor: ligar o painel na parte que guarda a história dos números",
  detalhe: "É o PR #1008. A medição está de pé e sabe responder, mas a lista de "
    + "senhas de máquina dela nasce vazia de propósito: hoje nem o painel "
    + "entra. Criar essa senha é passo que só você pode dar, porque senha não "
    + "viaja pela esteira de publicação. Cole na janela do servidor (a que "
    + "começa com deploy@srv ou root@srv, nunca a do seu computador):\n\n"
    + "curl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-da-medicao.sh -o /tmp/p.sh && bash /tmp/p.sh\n\n"
    + "Ele gera a senha dentro do servidor, escreve dos dois lados, confere se "
    + "bateu e termina dizendo PRONTO. A senha não aparece na tela. Rodar de "
    + "novo é seguro: o que já existe é reusado, nunca trocado. Se algo estiver "
    + "fora do lugar ele para sozinho com PAROU POR SEGURANÇA, sem ter mexido "
    + "em nada. Me mande a última tela.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1008",
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,
  se_eu_nao_decidir: "O painel continua sabendo só o presente: a medição acumula a história, e ninguém consegue lê-la.",
  recomendacao: "Rodar quando puder: leva menos de um minuto e não derruba nada do que está no ar.",
  reversivel: true,
  impacto: "medio"
});})();
