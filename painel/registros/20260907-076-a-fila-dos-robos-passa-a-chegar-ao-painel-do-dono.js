(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260907-076-a-fila-dos-robos-passa-a-chegar-ao-painel-do-dono",
  tipo: "entrega",
  quando: "2026-09-07",
  titulo: "A fila dos robos passa a chegar ao painel do dono",
  detalhe: "Nova rota painel/fila.json (protegida como qualquer pagina desta area, sempre 200) para a futura aba Prioridades do painel: le o que o build ja materializou (fila_embutida/estados.json) e traduz com as mesmas funcoes que a aba Os robos ja usa, sem recalcular nada.\\n\\nSo tarefas abertas aparecem. Cada tarefa tenta descobrir sua area do site pelo painel/areas.json (que ainda nao existe neste repositorio); enquanto ele nao existir, a rota responde com area vazia em todas e um aviso explicando o motivo, nunca com erro na pagina.\\n\\n9 testes novos, 3 provados por mutacao (filtro das abertas, quem espera o dono, e a resolucao de area), 1542 testes verdes na celula.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1340",
  verificado_em: "2026-09-07",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "fabrica",
  area: "admin",
  vence_em_dias: null,
  portao: null
});})();
