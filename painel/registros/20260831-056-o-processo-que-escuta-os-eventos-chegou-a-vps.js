(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-056-o-processo-que-escuta-os-eventos-chegou-a-vps",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Resolvido: o processo que escuta os eventos chegou ao servidor",
  detalhe: "Fecha o aviso que te dei ha pouco. O ultimo pedaco da gamificacao, aquele que nao tinha chegado ao servidor, chegou. A gamificacao esta completa ate onde combinamos hoje.\n\nO QUE TINHA ACONTECIDO: a publicacao falhou por atrito de rede (tempo esgotado na conexao com o servidor, tres vezes, com o servidor vivo). Voce escolheu tentar de novo; a tentativa foi CANCELADA por outros trabalhos entrando ao mesmo tempo. Voce entao escolheu forcar com um trabalho pequeno, e foi o que funcionou.\n\nA LICAO QUE ISSO DEIXOU, e ela ficou escrita dentro do proprio arquivo de configuracao, ao lado da peca que a custou: o catalogo da casa dizia 'repetir resolve' para esse tipo de falha. Hoje descobrimos o limite dessa receita. Num dia movimentado, repetir NAO resolve, porque a repeticao ressuscita um trabalho antigo e o proximo que chega o cancela. O que funciona e criar um trabalho NOVO, que carrega o estado mais recente.\n\nA PROVA DE QUE CHEGOU DE VERDADE, e ela e melhor do que um simples verde: a aplicacao no servidor deu certo na PRIMEIRA das tres tentativas, e o passo que existe justamente para pegar mentira (o que se chama 'verde sem ter trocado nada e o pior verde') passou. Foi esse mesmo passo que, uma hora antes, tinha reprovado e impedido que a falha passasse despercebida.\n\nMedido de fora agora: a pagina de conquistas, a capa, o forum e o painel respondem todos normalmente.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/730 mergeado (commit 59eb40da), deploy-infra run 33418810267 completed/SUCCESS. O passo 'Validar, trocar com backup datado e aplicar (tentativa 1 de 3)' deu success (as tentativas 2 e 3 nem rodaram), e o guarda 'A infraestrutura foi mesmo sincronizada? (verde sem ter trocado nada e o pior verde)' passou. PROVA DE FORA: /conquistas/ 200, /conquistas/healthz 200, / 200, /forum/ 200, /admin/painel/ 302 (redirecionamento de login, o esperado).",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: "20260831-046-o-ultimo-passo-da-gamificacao-nao-chegou-a-vps",
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
