(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-027-falta-uma-linha-sua-para-o-sino-acender",
  tipo: "pendencia",
  quando: "2026-08-27",
  titulo: "O sino e a tela de avisos da Caixa estão prontos — falta uma linha sua na VPS para eles acenderem de verdade",
  detalhe: "O QUE EU PRECISO DE VOCÊ: uma linha de comando, dentro da VPS, sem precisar digitar nem colar senha nenhuma — o script gera as duas sozinho.\n\nPOR QUE NÃO POSSO FAZER SOZINHO: é configuração que vive só na VPS, e o agente não tem acesso a ela (Lei 5 do projeto). É o mesmo tipo de passo que você já fez outras vezes esta semana.\n\nO QUE ACONTECE SE VOCÊ AINDA NÃO RODAR: nada quebra. O sino continua invisível ao lado do seu nome, e a tela de avisos da Caixa continua avisando 'não consegui buscar seus avisos agora' — os dois comportamentos são de propósito, não erro.\n\nO BLOCO PARA COLAR — DENTRO DA VPS (o prompt do terminal começa com deploy@srv... ou root@srv..., nunca com PS C:\\>):\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-porta-de-avisos.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nNão pede nenhum dado seu — sem senha para colar, sem e-mail, sem nada para digitar. Silêncio durante a execução é normal; ao final ele mostra 'PRONTO'. Pode rodar mais de uma vez sem medo — rodar de novo não desconfigura nada.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/318 — MERGED; infra/provisionar-porta-de-avisos.sh testado por encenação (rodadas repetidas, par divergido reconciliado, diretório errado recusado, recarregamento medido com docker falso) antes de propor",
  verificado_em: "2026-08-27",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "comunidade",
  vence_em_dias: null
});})();
