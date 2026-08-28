(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-074-a-gestao-da-caixa-mora-num-lugar-so",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "Está cumprido: a gestão da Caixa mora num lugar só, e é o Admin",
  detalhe: "A mudança que você pediu está inteira. Não existem mais dois lugares para conduzir as ideias dos alunos — existe um, e é meshcraft.top/admin/caixa/.\n\nO QUE VOCÊ FAZ LÁ AGORA, sem sair do Admin: ver o que espera por você, ver onde as ideias entopem, ver quem está sem resposta, abrir uma ideia por dentro com a história inteira dela, mudar a fase, escrever a avaliação da equipe e assinar a obra.\n\nOS ENDEREÇOS ANTIGOS NÃO FORAM APAGADOS — eles redirecionam. Um endereço que morre pune justamente quem o tinha salvo, e quem salvou foi quem mais usava a tela. E eles continuam atrás do crachá: quem não é da equipe leva a recusa antes de saber para onde a gestão foi.\n\nA CAIXA VOLTOU A SER SÓ O LUGAR DO ALUNO: escrever, votar, comentar, acompanhar, receber aviso. Nada mudou para ele.\n\nDUAS COISAS QUE SÓ APARECERAM CONSTRUINDO, e que teriam virado buraco se eu não tivesse parado para resolvê-las:\n\n1. A tela antiga mostrava o HISTÓRICO de cada ideia, e o combinado entre as duas partes não carregava isso. Aposentá-la sem resolver faria a história de cada ideia ficar inalcançável. Foi a terceira e última emenda daquele combinado.\n\n2. Contar PESSOAS não é somar as contagens de cada ideia: quem está atrás de duas seria contado duas vezes. Só a Caixa consegue fazer essa dedução, então três números viajam prontos de lá. Há um teste que monta exatamente esse cenário e exige o número certo.\n\nO QUE FICOU DE FORA, e é de propósito: a aba \"Os robôs\" continua apagada, esperando uma fonte de dados que não existe em lugar nenhum do projeto. E as telas de moderação antigas (/forms/sugestoes/moderacao) ainda existem — elas fazem o mesmo que a tela nova de detalhe, e seguem o mesmo caminho num próximo passo.",
  autoridade: "github",
  evidencia: "PRs mergeados: https://github.com/abundanciabr/sitesdoreino/pull/412 e /413 (a história no combinado e a Caixa contando-a), /416 (as ações dentro do Admin, com auditoria nos três desfechos) e /424 (as três telas antigas virando redirecionamento). Deploys 33215153509 e 33217038176, ambos completed/success lidos por gh run view --json status,conclusion. Prova de fora, na internet pública: /forms/sugestoes/gestao, /gestao/travessia e /gestao/esperando respondem 302 (o crachá vem antes do redirecionamento, como projetado); /admin/caixa/ responde 302; e a Caixa do aluno (/forms/sugestoes/ e /avisos) segue respondendo. Suítes: sugestoes 505 → 464 (as três abas levaram os testes delas), admin 186 → 218. Freeze do contrato PASS com 6 operações; guarda_dos_guardas PASS com 30 guardas em 21 invariantes, todos em disco.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  vence_em_dias: null
});})();
