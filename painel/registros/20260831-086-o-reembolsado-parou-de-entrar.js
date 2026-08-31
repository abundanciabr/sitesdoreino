(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260831-086-o-reembolsado-parou-de-entrar",
  tipo: "entrega",
  quando: "2026-08-31",
  titulo: "Passo 3 de 5 do reembolso: a partir de agora o reembolsado nao entra em lugar nenhum",
  detalhe: "ESTE E O PASSO EM QUE A SUA DECISAO VIRA COMPORTAMENTO. Os dois anteriores foram a lei e o combinado entre as pecas; aqui a porta mudou de verdade.\n\nO QUE UMA PESSOA REEMBOLSADA ENCONTRA A PARTIR DE AGORA: nada. Nao entra no curso, nao entra na Caixa de Sugestoes, nao entra no forum, nao entra na gamificacao. E isso acontece em TODOS esses lugares de uma vez, sem eu ter mexido em nenhum deles — porque existe uma pergunta so, 'esta pessoa e aluna?', e todas as partes do sistema fazem essa mesma pergunta para o mesmo lugar. Foi essa qualidade do desenho que tornou a regra antiga tao dificil de mudar, e e a mesma que a torna barata agora.\n\nO SISTEMA APRENDEU A DIZER 'REEMBOLSADO'. Parece detalhe e nao e. Sem essa palavra nova, quem fosse reembolsado passaria a ser descrito como 'apenas cadastrado' — ou seja, como alguem que nunca pediu nada — e veria o formulario de pedir entrada, do zero, como se a historia dele nao existisse. Esse foi exatamente o defeito que VOCE encontrou em 28/08 com o ex-aluno, na sua propria conta. Nao repeti.\n\nA SUA ESCOLHA DE 'SEM PEDIR PARA VOLTAR' TEM TRAVA DE VERDADE, e nao so uma tela sem botao. Se a recusa vivesse so no desenho da pagina, bastaria alguem mandar o pedido por fora para furar. Agora quem foi reembolsado e recusado na porta mesmo. E o ex-aluno CONTINUA podendo pedir para voltar, que e a sua decisao de 29/08 intacta — a diferenca entre os dois casos tem teste proprio, para ninguem 'simplificar' os dois no mesmo balde depois.\n\nAS TRAVAS DA REGRA ANTIGA VIRARAM TRAVAS DA REGRA NOVA. Elas nao foram apagadas: mudaram de lado. Quem tentar devolver o acesso ao reembolsado no futuro vai encontrar teste vermelho apontando para a sua decisao de hoje, do mesmo jeito que eu encontrei a de 24/08 apontando para o contrario. Trava que some depois de usada nao protege a proxima decisao.\n\nCOMO EU SEI QUE FUNCIONA, e nao so que 'passou': eu quebrei o codigo de proposito, duas vezes, e conferi que a quebra tinha REALMENTE sido aplicada antes de acreditar no resultado. Devolver o acesso ao reembolsado deixa 8 testes vermelhos; tirar so a trava da fila deixa 2. Essa conferencia da sabotagem existe porque em 28/08 uma sabotagem minha nao foi aplicada, o teste passou, e por um instante pareceu que o guarda nao servia.",
  autoridade: "github",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/762 — services/alunos: models.py (STATUS_QUE_VALEM encolheu para (ativa,), nasceu STATUS_QUE_BARRAM_A_FILA), services.py (a categoria 'reembolsado' e a recusa da fila) e api.py (o espelho do contrato). Medido nesta sessao: 146/146 da suite da celula em Postgres de verdade; contrato/alunos PASS, identico ao congelado (935 linhas comparadas); seguranca/alunos PASS com 9 operacoes conferidas na fonte; black limpo. Provas por mutacao, com a sabotagem conferida antes do resultado: devolver reembolsada a STATUS_QUE_VALEM = 8 vermelhos (inclusive o guarda antigo test_status_novo_nasce_sem_acesso, que pegou sozinho); tirar reembolsada de STATUS_QUE_BARRAM_A_FILA = 2 vermelhos. As tres descricoes do espelho em api.py foram lidas do YAML congelado, nunca redigitadas.",
  verificado_em: "2026-08-31",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "site",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
