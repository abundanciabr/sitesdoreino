(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260826-018-a-trava-entrou-na-main",
  tipo: "entrega",
  quando: "2026-08-26",
  titulo: "A trava de merge foi provada no próprio PR que a documenta — e ele entrou",
  detalhe: "O PR #226 (que escreve nos documentos do projeto que a trava existe) serviu de cobaia dela. Enquanto as duas provas do robô não ficaram verdes, o GitHub manteve o PR como 'bloqueado' — e nem o robô, nem você como dono da conta, conseguiriam mergear. Quando as provas ficaram verdes, o estado virou 'liberado' sozinho e o merge passou pelo caminho normal.\n\nÉ o ciclo completo, medido no mesmo dia: vermelho barra, verde libera.\n\nUm atraso honesto, que não foi culpa do projeto: o GitHub teve uma pane de mais de duas horas na esteira de testes. Nesse período nenhum teste conseguia nem começar, e o PR ficou parado sem veredito nenhum. A pane passou, os testes rodaram em 30 segundos e tudo entrou. Ficou registrado o que fazer da próxima vez, para ninguém perder uma hora achando que o problema era nosso.\n\nDepois do merge, as duas rondas automáticas da main rodaram e ficaram verdes. Nada de servidor foi tocado — este PR só mexe em documentos.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/226 — MERGED em 2026-08-26T18:54:49Z, commit 356d188f; estado do PR passou de BLOCKED para CLEAN quando muralhas e ci-celula-gate ficaram verdes; rondas pos-merge alarme-main (run 33002306828) e ci-celula (run 33002307021) ambas success",
  verificado_em: "2026-08-26",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: null,
  vence_em_dias: null
});})();
