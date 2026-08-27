(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260827-026-a-barra-no-final-parou-de-dar-erro-no-site-inteiro",
  tipo: "entrega",
  quando: "2026-08-27",
  titulo: "Endereço com barra no final parou de dar erro no site INTEIRO (as 4 peças)",
  detalhe: "Aquele problema que você tropeçou hoje — o mesmo endereço funcionar sem a barra no final e dar \"página não encontrada\" com ela — estava consertado só na Caixa. Agora está nas quatro peças do site: as páginas públicas, a entrada, o quiz e a Caixa.\n\nA que mais importava era a ENTRADA. O endereço de entrar com o Google dava \"não encontrado\" se tivesse uma barra a mais: a pessoa não conseguia nem tentar entrar na plataforma. Isso está resolvido.\n\nConferido ao vivo, no site de verdade, depois do deploy: as páginas de cadastro e login, a entrada do Google, e o endereço em espanhol (que preserva o idioma — quem estava no /es continua no /es, não é jogado para outra língua).\n\nO cuidado que isso exigiu, porque mexer em endereço é fácil de fazer errado: a regra só age quando o endereço COM barra não existe E o sem barra existe. Ou seja, ela é incapaz de mudar o destino de qualquer endereço que já funcionava. No quiz isso foi crítico — lá a página principal é canônica COM barra, e uma regra descuidada teria posto o site em laço infinito, recarregando para sempre. Tem teste medindo exatamente esse laço.\n\nE em todas as quatro: formulário enviado (POST) nunca é redirecionado. Um redirecionamento nesse caso apaga o que a pessoa preencheu em silêncio — perderia leads no funil, respostas no quiz, e no caso da entrada faria alguém \"sair\" sem sair de verdade.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/315",
  verificado_em: "2026-08-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "site",
  vence_em_dias: null
});})();
