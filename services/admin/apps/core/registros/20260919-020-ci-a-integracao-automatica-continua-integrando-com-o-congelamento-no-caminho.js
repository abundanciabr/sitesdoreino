(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260919-020-ci-a-integracao-automatica-continua-integrando-com-o-congelamento-no-caminho",
  tipo: "medicao",
  quando: "2026-09-19",
  titulo: "A integracao automatica continua integrando com o congelamento no caminho",
  detalhe: "Medicao pedida antes de mexer no mecanismo que integra todos os PRs da casa.\n\nO PR 1739 entrou na linha principal as 00:46:33 e levou consigo a consulta ao congelamento. Quatro minutos depois, as 00:50:19, a propria integracao automatica ja rodando com o codigo novo integrou o PR 1749, e as 00:55:43 integrou o PR 1752. O relatorio de um desses ciclos, lido no proprio registro do servico, mostra a linha nova ao lado das antigas: congelamento PASS, nenhuma celula congelada, sem mudar o veredito de nenhuma outra conferencia.\n\nO ciclo completo do congelamento tambem foi exercitado contra o servidor de verdade, numa celula sem trabalho aberto: ligar, ler, renovar, listar e desligar, com a marca removida ao fim. Com a celula congelada, a entrega daquela celula e a que toca a infraestrutura foram recusadas; a de outra celula passou.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1739 e https://github.com/abundanciabr/sitesdoreino/pull/1752, integrados por abundanciabr nos commits 484c01d3351b2a0c425faff6602fba6d37c9504b e 95c5e718e626aa5fc5773e7ec17e2fdce90c9c79, conferidos por gh pr view.",
  verificado_em: "2026-09-19",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,
  porque_so_voce: null,
  proximo_passo: null
}); })();
