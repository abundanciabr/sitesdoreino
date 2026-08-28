(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260828-064-o-sistema-para-de-chamar-ex-aluno-de-cadastrado",
  tipo: "entrega",
  quando: "2026-08-28",
  titulo: "O sistema parou de chamar quem saiu da escola de 'cadastrado' — era mentira sobre a pessoa",
  detalhe: "Isto é de outra frente, entregue hoje. Registro porque ninguém tinha contado a você e a porta do merge cobrou.\n\nO QUE ESTAVA ERRADO: quando alguém perguntava ao sistema 'quem é essa pessoa?', quem tinha a matrícula pausada ou encerrada voltava como 'cadastrado' — como se nunca tivesse estudado ali. Era mentira, e tinha uma consequência concreta: quem saiu da escola via o formulário de PEDIR ENTRADA, como se nunca tivesse pedido nada na vida. Você mesmo topou com isso ao usar o botão de apagar.\n\nO QUE MUDOU: agora existem dois nomes novos e honestos — 'pausado' (matrícula suspensa) e 'ex-aluno' (matrícula encerrada). O sistema passou a saber dizer a verdade sobre a pessoa.\n\nO QUE NÃO MUDOU, e é o que importa para a segurança: o acesso. Os dois estados já bloqueavam desde a manhã de hoje. Existe um teste afirmando que dizer o nome certo NÃO abriu porta nenhuma — é o guarda que separa 'consertei a tela' de 'afrouxei a porta'.\n\nA ordem em que o sistema decide é 'o mais acionável primeiro': aluno, na fila, pausado, ex-aluno, cadastrado. Quem espera uma decisão sua vem antes de quem já recebeu uma.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/400 (emenda de contrato) e https://github.com/abundanciabr/sitesdoreino/pull/401 (a celula alunos), sob a lei do PR #399. MERGED em 28/08/2026, conferidos por gh pr view. Prova declarada nos PRs: mutacao devolvendo 'cadastrado' para os dois de novo => 3 vermelhos; contrato-check PASS; services/alunos 111/111 em Postgres; black limpo. Registro escrito por sessao diferente da que entregou — divida cobrada pela porta do merge a quem chegou depois.",
  verificado_em: "2026-08-28",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,

  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: true,
  impacto: null
});})();
