(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-032-um-guarda-que-parecia-guardar-e-nao-guardava",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "Antes de dizer 'dívida fechada', conferi um por um — e três peças não estavam protegidas de verdade",
  detalhe: "Eu ia escrever que a dívida da hora estava fechada. Antes de escrever, fui contar os protetores em disco, um por um. Não fechava.\n\nDUAS PEÇAS (a área administrativa e a do login) tinham a configuração certa e NENHUM protetor. Nascer certo não é continuar certo: uma linha de configuração é a coisa mais fácil do mundo de se perder num merge, e ninguém acusaria.\n\nA TERCEIRA É A QUE DÓI. A Caixa de Sugestões — justamente a peça onde esse defeito foi descoberto — estava listada no documento como 'corrigida COM protetor que morde'. O protetor existia e NÃO mordia. Apaguei a configuração de propósito, com banco de dados de verdade, e ele continuou verde.\n\nPOR QUÊ: ele comparava a data da tela com o resultado da MESMA conversão que a tela usa. Apagando a configuração, os dois lados vão juntos para o fuso errado e a comparação continua batendo. Ele provava o formato da data — que é útil — mas não provava qual fuso estava valendo. O nome dele prometia mais do que ele entregava, e o documento acreditou na promessa.\n\nCONSERTADO em três PRs (239, 240 e 241), sem afrouxar nada: não toquei no protetor antigo, que continua provando o que sempre provou. Entrou um protetor novo do lado, medindo contra um valor fixo em vez de contra a própria conversão. Provei os dois lado a lado, com a configuração apagada: o novo fica vermelho, o velho fica verde.\n\nA REGRA VIROU MEMÓRIA DA CASA: o valor esperado de um teste nunca pode ser produzido pela mesma engrenagem que o teste existe para vigiar. E, ao declarar uma dívida fechada, contar os protetores em disco e sabotar um por um — frase de documento não é medição.",
  autoridade: "sessao",
  evidencia: "PRs #239, #240 e #241 MERGED, deploys success; prova lado a lado com Postgres real: sem TIME_ZONE, o guarda novo da sugestoes falha (offset -1 day, 19:00:00) e o antigo passa (1 passed); armadilhas/129",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null
});})();
