(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260829-062-a-porta-lateral-voce-escolheu-o-caminho-sem-risco",
  tipo: "decisao",
  quando: "2026-08-29",
  titulo: "Porta lateral do servidor: você escolheu o caminho sem risco — falta só você colar UMA linha",
  detalhe: "O QUE EU MEDI, E QUE MUDOU O PEDIDO: o item estava escrito desde 23/08 propondo um firewall que só aceitasse tráfego vindo do Cloudflare. Fui medir de fora antes de montar qualquer coisa. O site meshcraft.top responde DIRETO, sem Cloudflare na frente; o basileiatoutheou.org está atrás do Cloudflare. Ou seja: aquela regra derrubaria o meshcraft.top inteiro, no ato. Ela segue descartada — e agora com medição, não com lembrança.\n\nSUA DECISÃO, com as três opções na mesa: fazer o que dá hoje sem risco, e NÃO pôr o meshcraft.top atrás do Cloudflare (isso reabriria a decisão que você tomou em 23/08 de servi-lo direto).\n\nO QUE JÁ ESTÁ PRONTO: o script está no servidor, versionado. Ele garante que, além do SSH e das duas portas do site, nenhuma outra porta responda da internet. Não derruba nada, é seguro rodar duas vezes, e só diz PRONTO depois de conferir sozinho que o site continua no ar.\n\nO QUE ELE NÃO FAZ, e está escrito dentro dele: não esconde o endereço do servidor. Isso era a outra opção, que você recusou. A exposição que resta é fraca — robôs de varredura acham endereço de servidor de qualquer jeito, e o SSH já só aceita chave.\n\nFALTA VOCÊ: colar uma linha na janela da VPS. Enquanto não colar, este pedido fica aqui — é honesto, porque ele realmente espera por você.",
  autoridade: "mantenedor",
  evidencia: "Decisao do mantenedor em 29/08/2026. Medicao de fora na mesma sessao: 'curl -I https://meshcraft.top/' devolve 'Server: uvicorn' SEM cabecalho cf-ray (servido direto); 'curl -I https://basileiatoutheou.org/' devolve 'Server: cloudflare' com CF-RAY (atras do Cloudflare). Script entregue no PR https://github.com/abundanciabr/sitesdoreino/pull/469 (MERGED): infra/fechar-porta-lateral.sh.",
  verificado_em: "2026-08-29",
  precisa_do_dono: true,
  responde_a: "20260823-001-h15-porta-lateral-do-servidor",
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: "Nada quebra e nada piora — o servidor fica como esta hoje. A exposicao e fraca (o SSH ja e so por chave, e o banco e o Redis nunca responderam pela internet). O que se perde e a garantia MECANICA de que nenhuma porta nova apareca sem ninguem notar.",
  recomendacao: "Colar a linha quando tiver 1 minuto. E uma linha so, na janela da VPS (o texto comeca com deploy@srv... ou root@srv...). O script para sozinho se algo estiver estranho, e confere que o site continua no ar antes de dizer PRONTO.",
  reversivel: true,
  impacto: "baixo"
});})();
