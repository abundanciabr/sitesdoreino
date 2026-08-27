(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-004-um-alarme-de-seguranca-interno-falhava-so-neste-pc",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Um teste da muralha de segurança falhava só neste computador — corrigido, sem risco para o site",
  detalhe: "Enquanto preparava outra entrega (o mapa técnico do projeto para IA), uma sessão notou que um dos testes que provam que a 'muralha' funciona — o mecanismo que impede dois robôs de trabalharem na mesma pasta ao mesmo tempo e apagarem o trabalho um do outro — estava reprovando neste computador. Confirmou que não era culpa da entrega em andamento: o mesmo teste, isolado, reprovava até numa cópia limpa do projeto.\n\nA CAUSA era um detalhe técnico de como o Windows às vezes lê um caractere invisível que o PowerShell coloca no início de certos textos — em algumas configurações, esse caractere vinha corrompido antes de chegar ao robô, e o alarme de segurança, programado para recusar sempre que não conseguir entender o que está lendo (por segurança, nunca o contrário), recusava também esse texto corrompido.\n\nISSO NUNCA AMEAÇOU O SITE NEM TRAVOU NENHUMA ENTREGA: o portão que de fato decide se um PR pode ser aceito roda num computador Linux, do jeito que a produção roda — e nesse computador o teste sempre passou limpo. O defeito só aparecia rodando por engano os testes internos neste PC Windows específico.\n\nCORRIGIDO agora: o robô passou a ler o texto de um jeito que não depende mais dessa configuração do Windows — testado nos dois lados (o teste que falhava agora passa; os outros 35 testes da mesma muralha continuam passando). A lição já tinha sido escrita para a casa (armadilhas/138) quando encontrada; voltei ao mesmo arquivo e marquei como resolvida, para ninguém investigar de novo algo que já foi consertado.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/270 — MERGED (commit 2ccd31e20b06, confirmado via gh pr view --json state,mergedBy,mergeCommit); checks detectar/muralhas/ci-celula-gate PASS, ci-celula skipping (PR não toca services/); armadilhas/138 atualizada para RESOLVIDO no mesmo PR",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
