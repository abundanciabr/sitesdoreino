(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-052-um-comando-seu-liga-a-caixa-no-admin",
  tipo: "pendencia",
  quando: "2026-08-28",
  titulo: "Um comando seu, de uma linha, faz a Caixa aparecer dentro do Admin",
  detalhe: "As telas de meshcraft.top/admin/caixa/ já existem, mas abrem dizendo que não conseguiram perguntar. Falta uma senha compartilhada entre as duas partes do sistema — e senha não pode viajar pela esteira automática, por lei do projeto. Só existe se você a criar no servidor.\n\nO QUE VOCÊ FAZ: entra no servidor e cola UMA linha. Ela não pergunta nada, não pede nada, e a senha é gerada lá dentro — não passa por mim, não aparece na tela, não entra no repositório.\n\ncurl -fsSL https://raw.githubusercontent.com/abundanciabr/sitesdoreino/main/infra/provisionar-par-da-caixa.sh -o /tmp/p.sh && bash /tmp/p.sh\n\nONDE COLAR: dentro do servidor. Você sabe que está lá quando a linha do terminal começa com deploy@srv... ou root@srv... — se começar com PS C:\\>, você ainda está no seu computador e o comando não vai funcionar.\n\nO QUE ESPERAR NA TELA: ele mostra o que encontrou, o que mudou e termina com \"PRONTO: a Caixa de Sugestões está ligada dentro do Admin\". Se algo estiver estranho, ele para sozinho com uma frase que começa com \"PAROU POR SEGURANÇA\" e não mexe em nada — nesse caso me mande a tela inteira.\n\nRODAR DE NOVO É SEGURO. Se a senha já existir, ele reusa em vez de trocar. Na dúvida, rode.\n\nSE A TELA DISSER QUE NÃO ACHOU UM DOS ARQUIVOS: alguma das duas partes ainda não subiu com a versão nova. Espere alguns minutos e rode de novo.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/397 (o script versionado, com 12 testes que o EXECUTAM contra uma plataforma de mentira: nenhum segredo na tela, rodar de novo não rotaciona, o par bate dos dois lados, e toda recusa para sem escrever nada).",
  verificado_em: "2026-08-28",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: "As três abas de /admin/caixa/ continuam abrindo com o aviso de que não conseguiram perguntar — inúteis, ainda que construídas e no ar. Nada quebra e nada sai do ar; o que fica parado é o uso. E enquanto isso a gestão continua acontecendo pelas telas antigas da Caixa, que é justamente o espalhamento que você mandou acabar.",
  recomendacao: "Rodar hoje, ou quando abrir o servidor pela próxima vez. É uma linha, não pergunta nada, e rodar de novo é seguro. Não há decisão embutida: o comando não escolhe nada por você — só cria a senha que as duas partes precisam para conversar.",
  reversivel: true,
  impacto: "medio"
});})();
