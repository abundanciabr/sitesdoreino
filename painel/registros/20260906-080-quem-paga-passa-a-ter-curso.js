(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260906-080-quem-paga-passa-a-ter-curso",
  tipo: "entrega",
  quando: "2026-09-06",
  titulo: "Degrau 4 e ultimo: quem paga passa a ter curso, e o buraco fecha",
  detalhe: "Este e o fecho do que voce mandou fazer hoje. Ate agora, quem PAGAVA virava aluno ativo sem curso nenhum, calado, e nao conseguiria abrir sala nenhuma. Agora a matricula que nasce de uma compra ja diz de qual produto ela e.\n\nO CASO QUE MAIS IMPORTA nao e o normal, e o torto: uma compra que chegue SEM o produto. Vai acontecer (aviso antigo ainda na fila, reprocessamento). A matricula nasce assim mesmo, porque A PESSOA PAGOU e o dinheiro dela nao pode depender de um campo que alguem esqueceu. O caso fica anotado com o numero do pedido, para dar para achar a pessoa depois.\n\nO QUE NAO SE FAZ E ADIVINHAR: nao existe curso padrao, pelo mesmo motivo que a tela de liberar nao tem opcao ja marcada. O palpite faria a escolha errada parecer escolha.\n\nUMA SABOTAGEM MINHA NAO PEGOU, e eu nao apaguei a protecao: escrevi o teste que a mede onde ela vale, e ela passou a pegar. Sem ela, um aviso mal formado gravaria a palavra 'None' como se fosse um curso.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/1222 (PR #1222). Suite da celula alunos em PostgreSQL real: 207 passed (antes: 200). Prova por mutacao, cinco sabotagens, cada vermelho na assercao: volta a gravar vazio, o aviso some, o aviso perde o numero do pedido, o aviso passa a sair sempre virando ruido, e a peneira do or vazio (assert 'None' == ''). black --check limpo e contract_freeze alunos PASS.",
  verificado_em: "2026-09-06",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
