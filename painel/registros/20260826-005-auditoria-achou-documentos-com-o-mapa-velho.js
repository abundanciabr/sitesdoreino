(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-005-auditoria-achou-documentos-com-o-mapa-velho",
  tipo: "incidente",
  quando: "2026-08-26",
  titulo: "A auditoria achou uma falha real da obra: 7 documentos ainda mandavam usar o painel morto",
  detalhe: "A lei mudou no CLAUDE.md, mas a varredura dos documentos ficou de fora da obra — e ela estava no escopo (uma das consultorias avisou: 'a migração dos hábitos é parte da obra, não acabamento'). O pior caso era o PLAYBOOK.md, o PRIMEIRO documento que toda sessão lê: ele dizia que o agente NÃO consegue editar o painel por estar fora do Git — exatamente o contrário do que passou a valer. Uma sessão nova leria isso e iria atrás do painel morto.\n\nCorrigidos nesta varredura: PLAYBOOK.md, ARMADILHAS.md (a tabela 'onde cada coisa mora' e o bloco que explicava por que o painel não era versionado), ARMADILHAS-OPERACAO.md (as seções 7.2 e 7.4, que ensinavam o método antigo), PROMPTS-INICIAIS.md (2 lugares), RUNBOOK-LOTES.md (2 lugares), o molde de despacho da Caixa e uma nota no plano da área administrativa.\n\nFICA PARA DEPOIS, por regra da casa: services/checkout/LICOES.md e services/pagamentos/LICOES.md também citam o painel velho, mas são CÉLULAS DIFERENTES e a cerca do CI proíbe um PR tocar duas. São menções de passagem, sem instrução errada. Entram de carona no próximo despacho que tocar cada uma dessas células.",
  autoridade: "sessao",
  evidencia: "PR da varredura pós-reforma (busca por 'painel-fundacao|painel-roadmap|painel-dados|arquivos/painel' em todo .md versionado)",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: null,
  vence_em_dias: null
});})();
