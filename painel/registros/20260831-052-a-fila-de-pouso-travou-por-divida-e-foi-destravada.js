(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-052-a-fila-de-pouso-travou-por-divida-e-foi-destravada",
  tipo: "incidente",
  quando: "2026-08-31",
  titulo: "A fila de pouso travou para todos os robos, e ja foi destravada",
  detalhe: "Os robos reclamaram que a fila estava travada, e a reclamacao era verdadeira: a pista de pouso estava recusando TODOS os pedidos de merge, um atras do outro.\n\nA causa nao era defeito na pista. Era a divida do livro: dois merges entraram na main sem que ninguem contasse a voce (primeiro o PR 694, depois o PR 697), e essa divida e compartilhada de proposito: ela fecha a porta para todo mundo ate alguem pagar. Cinco PRs prontos e verdes (721, 722, 723, 725 e 727) foram devolvidos pela pista so por causa dela, sem nenhum defeito proprio.\n\nO pagamento da divida do PR 697 entrou as 17h04 (PR 731, conferido: MERGED). Com a conta quitada, esta sessao pediu pouso de novo pelos cinco PRs devolvidos, esperando os checks de cada um pelo caminho autorizado (a espera que fala). A pista atende sozinha dali em diante.\n\nO buraco de raiz ja estava mapeado na memoria de campo (armadilha 214): quem fecha uma tarefa no balcao dos robos gera um comprovante que nao e perdoado pelo porteiro do livro, entao todo fechamento de tarefa cria uma divida nova e trava a fila outra vez. A cura de verdade (ensinar o porteiro a perdoar tambem quem so escritura no balcao) esta em andamento agora mesmo, no PR 733, aberto por outra sessao.\n\nVoce nao precisa fazer nada: foi atrito entre robos, resolvido entre robos.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/731",
  verificado_em: "2026-08-31",
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
