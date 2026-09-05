(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260905-081-a-lei-que-impede-a-ia-de-decidir-pelo-aluno",
  tipo: "entrega",
  quando: "2026-09-05",
  titulo: "A regra de que a IA nunca decide pelo aluno virou lei com fiscal",
  detalhe: "O ajudante de IA do curso rascunha o laudo, e a professora le, corrige e assina. A parte que MAIS importa e o que ele nao faz: nao decide se a porta do aluno abre, nao marca data e nao responde a pergunta do dia seguinte.\n\nAte agora isso era so uma promessa escrita. Agora e uma lei do sistema com um fiscal automatico: se alguem tentar dar a IA um campo para guardar decisao, o teste reprova e o codigo nao entra.\n\nPROVADO NA MARRA, nao no papel: eu mesmo dei um campo de decisao a IA de proposito e dois testes reprovaram na hora. Depois desfiz.",
  autoridade: "github",
  evidencia: "PR #1122. pytest tests/test_inv_l4_a_ia_nao_decide.py -> 7 passed contra o codigo ja em producao; sabotagem (campo decisao no dataclass) -> 2 failed nas assercoes; desfeita -> 7 passed. ci/ci.py --apenas guardas -> PASS; test_guarda_dos_guardas.py -> 47 passed.",
  verificado_em: "2026-09-05",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "verde",
  frente: "curso",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null
}); })();
