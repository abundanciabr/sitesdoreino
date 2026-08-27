(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-009-o-site-agora-abre-em-portugues",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "O site agora abre em português — meshcraft.top é português, e o inglês mudou de endereço",
  detalhe: "Você decidiu hoje: o site inteiro em português. Está no ar.\n\nO QUE MUDOU, na prática:\n\n· meshcraft.top/ — agora abre em PORTUGUÊS (antes abria em inglês)\n· meshcraft.top/en/ — agora é o endereço do inglês (antes não existia, dava erro)\n· meshcraft.top/pt-br/ — agora NÃO existe mais, dá erro. É o preço da mudança, e era esperado: o idioma principal do site mora no endereço nu, sem etiqueta. Como o português virou o principal, ele saiu de /pt-br/ e foi para a raiz.\n· o espanhol não mudou nada.\n\nPOR QUE ISSO CUSTOU UMA LINHA E NÃO UMA REFORMA: o projeto foi construído com o idioma sendo um DADO, não código. Trocar o padrão foi mudar uma palavra num arquivo de configuração; o resto do site se ajustou sozinho, porque todos os endereços públicos nascem de um lugar só.\n\nUMA COISA QUE ISSO RESOLVEU DE BRINDE: você tinha pedido que a Caixa de Sugestões tivesse 'pt-br' no endereço dela. A Caixa é escrita só em português, e com o inglês na raiz ela era uma ilha estranha. Eu ia precisar movê-la — e isso te custaria mais uma linha colada no servidor. Com o português na raiz, o endereço dela JÁ É o endereço português. Nada a fazer, nada para você colar.\n\nUM QUASE-ERRO MEU, que registro porque é instrutivo: medi o site logo depois do deploy ficar verde, vi que continuava em inglês, e quase te disse que tinha falhado. Não tinha — existe um cache de 1 minuto entre o servidor e as páginas. Medi de novo minutos depois e estava tudo certo. A casa já tinha a lição de 'não confie no relógio, confira o conteúdo'; aqui ela valeu ao contrário: medir CEDO DEMAIS também mente.\n\nA DECISÃO ANTIGA NÃO FOI DESFEITA, e isso importa para os próximos robôs: a regra de 25/08 ('o idioma principal mora na raiz, os outros levam etiqueta') continua inteira. Só trocou QUAL idioma é o principal. Deixei isso escrito em cima do documento daquela decisão, para ninguém 'consertar' de volta achando que foi engano.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/279 — MERGED (commit 4544655); deploy-infra 33091535307 completed/success; medido de fora DEPOIS da propagação: https://meshcraft.top/ responde 200 com lang=\"pt-BR\", /en/ responde 200 com lang=\"en\" (antes 404) e /pt-br/ responde 404 (antes 200); guarda do sites.json atualizado junto e provado por sabotagem (default_language=fr deixa vermelho)",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
