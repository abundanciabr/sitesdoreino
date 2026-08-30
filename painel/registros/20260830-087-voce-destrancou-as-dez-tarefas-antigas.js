(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-087-voce-destrancou-as-dez-tarefas-antigas",
  tipo: "decisao",
  quando: "2026-08-30",
  titulo: "Voce destrancou as dez tarefas antigas: elas voltaram para o balcao dos robos",
  detalhe: "Em 29/08/2026 voce congelou dez tarefas de bastidor, dizendo que as recomendacoes antigas ficariam para depois. Hoje voce mandou destrancar, e elas voltaram para o balcao. Qualquer robo pode pegar.\n\nSao estas, em portugues: fazer copia de seguranca do banco de dados antes de toda mudanca de estrutura · a senha do banco existir so dentro da publicacao, nunca solta · calcular os tempos de espera a partir do que foi medido, em vez de chutar · um robo revisor com cabeca fresca conferindo cada entrega antes dela entrar · um verificador de maiusculas e fim de linha · separar por assunto a conta de quantas perguntas os robos te fazem · uma trava que exige teste em cada parte do site · abrir a entrega em rascunho no primeiro minuto, como aviso aos outros robos · marcar como abandonado o que ficou para tras, sem apagar · e o versionado conferir se o que nao e versionado esta instalado.\n\nNenhuma delas te pede nada, e nenhuma muda o que o aluno ve. Sao todas de bastidor: servem para o proprio maquinario ficar mais seguro e mais rapido.\n\nO gesto foi o do balcao, e nao uma edicao: cada tarefa recebeu um acontecimento novo dizendo 'devolvida a fila'. Nenhum arquivo antigo foi mexido, e o estado continua sendo calculado, que e o que impede a fila de mentir sobre o que esta livre.",
  autoridade: "mantenedor",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/652 (este PR). Ordem dada por ele na sessao do Claude Code de 30/08/2026, em resposta a uma caixa de pergunta estruturada. Dez eventos 'devolvida' escritos pelo balcao (python ci/fila.py soltar). Conferido depois: python ci/fila.py validar responde 'Fila valida — 41 tarefa(s), 75 evento(s) (concluida: 28 · na fila: 13)', com ZERO bloqueadas, e as dez aparecem como 'na fila'. O congelamento anterior estava no registro 20260829-029.",
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
