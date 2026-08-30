(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-005-duas-entregas-nao-estavam-contadas-no-livro",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "Duas entregas de ontem à noite não estavam contadas no livro — agora estão",
  detalhe: "Ao atualizar o painel com o estado do projeto, o conferidor de contas do livro apontou duas entregas mergeadas na noite de 29/08 que ele não conseguia contar: a vitrine de ideias da Caixa (entrega 537) e a correção da placa que mandava o número do registro para o lado errado (entrega 538).\n\nO fato não estava perdido: as duas entregas levaram o próprio registro dentro delas. O que faltou foi o NÚMERO da entrega escrito na prova — uma delas ficou com a prova em branco, a outra descreve a prova por extenso mas diz apenas 'a entrega desta vez', sem o número. O conferidor procura número; sem número, ele conta como dívida. É o mesmo cuidado que já existe na lei, aparecendo pelo lado que ninguém tinha olhado: escrever a prova sem o número deixa a conta furada mesmo quando o trabalho está todo lá.\n\nComo registro que já foi mergeado nunca se edita, quem fecha a conta é este registro aqui, que cita as duas entregas pelo número. Conferido de fora agora: as duas constam como MERGED no GitHub, e a publicação do site que veio depois delas terminou em sucesso.\n\nNada aqui espera por você — é acerto de contabilidade do próprio livro.",
  autoridade: "github",
  evidencia: "As duas entregas conferidas uma a uma com `gh pr view --json state,mergedAt`: https://github.com/abundanciabr/sitesdoreino/pull/537 (MERGED em 2026-08-29T23:46:25Z) e https://github.com/abundanciabr/sitesdoreino/pull/538 (MERGED em 2026-08-29T23:37:39Z). A publicação da main que veio depois delas terminou verde: run 33284945180 (deploy-celula) e run 33284945160 (deploy-infra), ambos completed/success, lidos por `gh run list --json status,conclusion` e não pelo fim de um comando com cano pendurado. Depois deste registro, `ci/divida_do_livro.py` passa a contar zero entregas sem dono.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
