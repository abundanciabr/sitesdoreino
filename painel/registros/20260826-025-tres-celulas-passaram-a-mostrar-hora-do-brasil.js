(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-025-tres-celulas-passaram-a-mostrar-hora-do-brasil",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Três peças do site passaram a mostrar hora do Brasil — e ganharam um guarda que reprova se alguém desfizer",
  detalhe: "Havia uma linha de configuração que nunca foi escolhida nesta plataforma: a que diz QUE HORA MOSTRAR. Sem ela vale o padrão de fábrica da ferramenta, que é o fuso de Chicago — cinco horas atrás. Perto da meia-noite isso troca até o DIA na tela.\n\nO detalhe que torna isso perigoso: não é um erro. Não aparece vermelho em lugar nenhum, o site responde normal, e quem descobre é o visitante lendo a data errada.\n\nO QUE ENTROU HOJE: a linha certa em três peças — o site (funil), o catálogo e a que envia e-mails (mensageria) — cada uma com um teste que NÃO confere se a linha existe (isso seria conferir o próprio texto), e sim se a hora sai certa. Apaguei a linha de propósito antes de cada entrega e vi o teste ficar vermelho acusando '24/08/2026 23:00' onde devia ler '25/08/2026 01:00'. Depois repus e ficou verde.\n\nO caso do envio de e-mail era o mais grave dos três: uma hora errada numa tela se conserta; num e-mail já enviado, não.\n\nHONESTIDADE SOBRE O TAMANHO DO ESTRAGO: nenhuma dessas peças mostra data na tela hoje. O defeito estava dormindo, esperando a primeira página que mostrasse hora — foi assim que a Caixa de Sugestões foi pega em 24/08. Então isto não conserta nada que você veria hoje; impede o que você veria depois.\n\nTrês PRs, um por peça, os três mergeados com os portões verdes e a plataforma no ar o tempo todo (conferi de fora: os três endereços responderam 200 depois de cada entrega).",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/233 · /pull/234 · /pull/235 — os três MERGED, deploys 33013333493, 33013598246 e 33014036704 com conclusão success; meshcraft.top/healthz, meshcraft.top e basileiatoutheou.org em 200 depois da janela",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: "20260826-011-rumo-site-fuso-horario",
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
