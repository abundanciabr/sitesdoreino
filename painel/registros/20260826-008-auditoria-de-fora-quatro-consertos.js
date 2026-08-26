(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-008-auditoria-de-fora-quatro-consertos",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "Uma segunda auditoria, de sessão nova, achou quatro defeitos no painel — os quatro foram corrigidos",
  detalhe: "A obra da reforma foi auditada por uma sessão que não a construiu, com o painel aberto num Chrome de verdade (o que fecha a ressalva do registro 006: a costura entre o manifesto e os registros funciona — 18 registros carregaram, o placar calculou sozinho). O que estava de pé continua de pé. O que estava errado:\n\n1) O cartão 'As últimas conferências automáticas' pintava VERDE contando execução que ainda não tinha terminado. Medido ao vivo: 2 das 6 estavam na fila e o cartão dizia 'as últimas 6 execuções fecharam verdes'. Era o falso-verde nº 1 da casa dentro do instrumento feito para matá-lo. Agora, execução ainda correndo pinta CINZA 'sem veredito'.\n\n2) A caixa 'Precisa de você' CONSEGUIA esquecer, por três portas: o campo que põe o pedido nela escrito com aspas, o campo esquecido, e um registro que respondia a si mesmo. As três passavam pela validação e o pedido sumia calado. As três agora reprovam na entrada.\n\n3) A muralha do painel perdia o veredito do próprio instrumento: imprimia '(exit 0)' ao reprovar e rebaixava ERROR a FAIL. O estado que o teste dizia cobrir era o único que ninguém media.\n\n4) Rótulos que mentiam: dois documentos citavam um gerador '.py' que não existe, e duas listas anunciavam 3 muralhas quando são 4.\n\nFICA PARA VOCÊ DECIDIR, e está registrado como pedido separado: a vista 'Meu mapa' que o veredito prometeu não foi construída, e essa omissão não estava declarada.",
  autoridade: "sessao",
  evidencia: "PR #227 — vermelho→verde medido nos quatro: cartão verde com 2 de 6 execuções 'queued'; validação aprovando os 3 casos que esvaziavam a caixa; muralha devolvendo exit 1 com '(exit 0)' impresso onde devia ser 2. Portões depois: muralhas 4/4 PASS, testador 505 passed",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
