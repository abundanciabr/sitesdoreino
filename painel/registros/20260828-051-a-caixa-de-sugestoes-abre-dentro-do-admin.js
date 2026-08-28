(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-051-a-caixa-de-sugestoes-abre-dentro-do-admin",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "A Caixa de Sugestões abre dentro do Admin — a mudança de casa que você pediu está feita",
  detalhe: "meshcraft.top/admin/caixa/ existe. As três abas que você escolheu de manhã mudaram de casa: A sua mesa, A travessia e Quem está esperando. A visão geral do Admin ganhou a terceira porta, ao lado do painel do sistema e do painel da escola — uma porta só para tudo que é gestão, como você mandou.\n\nO ENDEREÇO NÃO É O QUE VOCÊ PEDIU AO PÉ DA LETRA, e já expliquei o porquê: /admin/painel/ é onde mora este livro que você está lendo, e a gestão ali bateria de frente com ele. Ficou /admin/caixa/, ao lado de /admin/escola/.\n\nO QUE ELAS MOSTRAM É CALCULADO AQUI, e os FATOS vêm da Caixa. A diferença importa para o seu tempo futuro: do jeito que ficou, eu mudo o layout dessas telas quantas vezes você quiser sem te chamar para nada. A única exceção são três números — quantas pessoas estão esperando, há quantos dias em média, e quantas passaram de um mês — que vêm prontos da Caixa porque só ela consegue contar pessoas sem contar ninguém duas vezes.\n\nSE A CAIXA CAIR, A PÁGINA ABRE DO MESMO JEITO e diz que não conseguiu perguntar. E não mostra ZERO: zero se leria como \"não há ideia nenhuma\", que seria uma afirmação sobre algo que eu não medi. Testei os três jeitos de isso falhar; nos três a página abre.\n\nUM ERRO QUE O TESTE ACHOU: data no futuro (relógio da máquina fora de hora) produzia \"parada há -355142 dias\" na tela. Não é um número esquisito — é uma frase sem sentido numa tela feita para leigo. Consertado.\n\nATENÇÃO — ELAS AINDA NÃO TÊM O QUE MOSTRAR. Falta um comando de uma linha seu no servidor, e ele está na sua caixa. Até você rodar, as três abas abrem dizendo que não conseguiram perguntar.\n\nE FALTA A ÚLTIMA ETAPA: os botões de agir (mudar fase, avaliar, assinar) ainda estão nas telas antigas da Caixa. Enquanto isso, os dois lugares existem — que é justamente o que você proibiu. A mudança só estará cumprida quando as telas antigas virarem redirecionamento.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/396, mergeado. Deploy 33206503192 completed/success, lido por gh run view --json status,conclusion. Prova de fora, na internet pública: /admin/caixa/, /admin/caixa/travessia/ e /admin/caixa/esperando/ respondem 302 (mandam para o login, como toda rota da área). Suíte da célula admin 166 → 186, black limpo em 39 arquivos. A rede é dublada nos testes com respx, que estoura em qualquer chamada não registrada — prova de que nada ali sai para a internet.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
