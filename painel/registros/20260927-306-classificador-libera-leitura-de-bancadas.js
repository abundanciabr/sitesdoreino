(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260927-306-classificador-libera-leitura-de-bancadas",
  tipo: "resposta",
  quando: "2026-09-27",
  titulo: "Mantenedor autoriza ajuste no classificador que travava bancadas de outras sessões",
  detalhe: "Ele perguntou por que os robôs ainda pedem aprovação para mexer em bancadas. Causa: o classificador recusava toda bancada wt-* de outra sessão e, após 3 recusas, chegava a pedir até um git status. O environment de ~/.claude/settings.json apontava para o repositório antigo, inexistente.\n\nDecisão: 'Pode ajustar'. Feito fora do repositório, em ~/.claude/settings.json: environment corrigido; regra nova 'Factory Benches' libera ler qualquer bancada sempre, e libera editar, commitar e dar push no ramo agent/* só após o ci/sessao.py a retomar e o balcão confirmar a tarefa. Apagar bancada, reset hard, clean e force push seguem bloqueados.",
  autoridade: "mantenedor",
  evidencia: "claude auto-mode config mostra 'Factory Benches' nas regras allow; git status na bancada wt-forum-comunidade-celular-e-teclado-no-forum passou sem pergunta.",
  verificado_em: "2026-09-27",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "fabrica",
  area: "painel",
  vence_em_dias: null
}); })();
