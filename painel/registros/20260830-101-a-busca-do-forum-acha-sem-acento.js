(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-101-a-busca-do-forum-acha-sem-acento",
  tipo: "entrega",
  quando: "2026-08-30",
  titulo: "A busca do fórum passou a achar sem acento: quem procura \"duvida\" acha \"dúvida\"",
  detalhe: "Você escolheu curar isso antes da inauguração, e está curado. Medido na internet depois da entrega, sem login: procurar \"duvida\" devolve 2 resultados, e procurar \"dúvida\" devolve os MESMOS 2. A mesma palavra, escrita das duas formas, acha as mesmas conversas.\n\nPor que isso importa mais do que parece: no Brasil quase ninguém acentua ao buscar. A versão anterior errava boa parte das buscas reais em silêncio, e o aluno concluía que a resposta não existia e perguntava de novo, que é o contrário do que um fórum serve para fazer.\n\nVocê rodou o passo do servidor e ele respondeu PRONTO. Uma coisa que vale registrar porque foi aprendizado: você rodou antes de o código novo subir, e por algumas dezenas de minutos o banco guardava as mensagens de um jeito enquanto o site procurava de outro. Nada se perdeu e ninguém ficou fora do ar, mas buscar com acento podia falhar nessa janela. A correção subiu junto e é automática: o próprio deploy reindexa tudo com a configuração ativa, então essa janela não volta na próxima vez.\n\nO que continua faltando, dito com honestidade: o plural em \"ens\" ainda não é unido, ou seja, quem procura \"modelagens\" não acha \"modelagem\". É outro conserto, de outro tipo (um dicionário), e está anotado no catálogo de armadilhas com o teste que o cobra.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/667 e o fecho em https://github.com/abundanciabr/sitesdoreino/pull/669 — suíte da célula 167 para 170 verdes, com o guarda do acento invertido (agora exige a cura nas duas direções); deploy-celula run 33342991511 completed/success nas duas células, lido por gh run view --json; prova de fora sem login: /forum/buscar?q=duvida e /forum/buscar?q=dúvida devolvem ambos '2 resultados'",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
