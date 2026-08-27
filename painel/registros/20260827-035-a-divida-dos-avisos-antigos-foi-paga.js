(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-035-a-divida-dos-avisos-antigos-foi-paga",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Achei e paguei uma dívida que ficaria escondida: avisos que você já tinha lido apareceriam de novo como 'novos'",
  detalhe: "Na auditoria de fechamento, achei um alerta que uma sessão anterior tinha deixado escrito para quem construísse o sino: quando os avisos antigos da Caixa foram copiados para a caixa central (26/08), eles chegaram lá marcados como 'não lidos' — porque naquela hora ainda não existia nenhuma tela lendo de lá. O alerta dizia, com todas as letras: antes de ligar o sino de vez, alguém precisa marcar esses avisos antigos como já lidos, senão todo mundo veria de novo, como novidade, coisa que já tinha lido há dias.\n\nEsse aviso não tinha sido atendido — nem o despacho que construiu o sino nem o que migrou a tela da Caixa cuidaram disso, porque nenhum dos dois estava olhando para aquele alerta específico. Corrigido agora: uma correção que roda sozinha assim que o servidor sobe (sem precisar de nada seu), identifica com certeza matemática quais avisos vieram daquela cópia antiga (usando a mesma fórmula que os criou, sem precisar espiar o banco de outra peça do sistema) e marca como lidos só esses — nunca um aviso genuinamente novo.\n\nTestei a correção de um jeito que prova que ela funciona de verdade: quebrei a fórmula de propósito e confirmei que o teste acusou a quebra (um aviso novo teria sido marcado como lido por engano) — só depois de ver o alarme disparar é que confio que ele protege alguma coisa.\n\nNão tenho como saber, daqui, quantos avisos foram corrigidos na prática (não tenho acesso ao banco de produção) — mas o site continuou respondendo normalmente durante e depois, o que confirma que a correção rodou sem quebrar nada.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/328 — MERGED, commit 1cce16a889a4; deploy-celula 33113006132 success; medido de fora depois: meshcraft.top e /forms/sugestoes/healthz em 200; teste de mutação provado (fórmula sabotada de propósito, teste acusou, revertido)",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null
});})();
