(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-019-as-doze-tarefas-das-mensagens-estao-no-balcao-trancadas",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "As doze tarefas das mensagens automaticas estao prontas no balcao — e trancadas esperando voce",
  detalhe: "Voce pediu que eu deixasse o trabalho pronto para as outras IAs. Esta feito.\n\nOs doze degraus do plano viraram doze tarefas na fila (TAR-054 a TAR-065), uma por degrau. Elas estao AMARRADAS UMA NA OUTRA: a que constroi a regua so libera depois que as tabelas existirem, a que poe a primeira sequencia no ar so libera depois do motor, e assim por diante. Isso nao depende de nenhum robo lembrar da ordem — o balcao calcula e recusa quem chegar fora de hora.\n\nTODAS NASCERAM TRANCADAS. As tres que nao dependem de nenhuma outra levam o aviso 'aguardando despacho do mantenedor'. Nenhum robo pega nada ate voce mandar — que foi exatamente o que voce pediu.\n\nCada tarefa carrega o proprio manual: o que ler antes de comecar, a lei daquele degrau que nao se negocia, e que prova fecha o trabalho. Tres exemplos do que ficou escrito la dentro para nao se perder: a trava que impede um cliente de receber dois e-mails do mesmo pagamento NAO pode ser tocada; nao existe trava de menor de idade porque a escola e 18+, e isso esta escrito como decisao e nao como esquecimento; e a tarefa dos enderecos que devolvem vem ANTES de mandar para lista grande, porque insistir num endereco que devolve e o que queima o dominio da escola.\n\nDUAS DAS DOZE PASSAM POR VOCE, e estao marcadas: a sessao de contrato (TAR-055), que por lei do projeto exige voce presente; e a escolha do provedor de e-mail (TAR-063), que envolve conta paga e configuracao de DNS. As outras dez sao trabalho de robo do comeco ao fim.\n\nPara soltar tudo, basta voce mandar. Para soltar so uma parte, me diga qual.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/683 (TAR-054..060) e https://github.com/abundanciabr/sitesdoreino/pull/685 (TAR-061..065). Sao o MESMO acontecimento em dois PRs porque 16 arquivos estouram o orcamento de 15 (armadilhas/035: divida em PRs, nunca peca a etiqueta). As doze tarefas tem depende_de encadeado e as tres raizes tem evento bloqueada; python ci/fila.py validar responde 'Fila valida'.",
  verificado_em: "2026-08-31",
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "info",
  frente: "curso",
  vence_em_dias: null,

  se_eu_nao_decidir: "As doze tarefas ficam paradas no balcao e nenhuma mensagem automatica e construida. Nada se perde e nada apodrece — elas esperam. Mas tambem nao anda: hoje a plataforma nao manda boas-vindas, nao manda incentivo, e nunca mandou um e-mail sequer.",
  recomendacao: "Soltar as TAR-054 e TAR-061 primeiro — sao as duas que nao dependem de voce para nada: emendar a constituicao da mensageria e fazer a gamificacao comemorar. Elas destravam metade da escada sozinhas. A sessao de contrato (TAR-055) e a escolha do provedor (TAR-063) voce marca quando tiver tempo.",
  reversivel: true,
  impacto: "alto"
});})();
