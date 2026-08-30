(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260830-082-a-escada-da-gamificacao-tinha-dois-degraus-trocados",
  tipo: "nota",
  quando: "2026-08-30",
  titulo: "A escada da gamificacao tinha dois degraus na ordem errada, e um robo achou antes de o estrago acontecer",
  detalhe: "O plano da gamificacao previa 22 entregas numa ordem. Dois degraus estavam trocados, e o erro so apareceria depois, travando toda a construcao da parte nova do site.\n\nO que aconteceu, em portugues: hoje foi congelado o combinado entre a gamificacao e o resto do site (o contrato). Congelar significa por o documento no lugar e trancar: dali em diante ninguem muda sozinho. So que o projeto confere esse combinado comparando o documento com o que a parte do site REALMENTE responde. E a gamificacao ainda nao responde nada: a porta pela qual ela conversa com as outras partes so estava prevista para muito mais adiante.\n\nResultado: o documento existe, a porta nao, e o conferidor reclama. O proximo trabalho na gamificacao morreria no teste, sem ninguem entender por que.\n\nO robo que congelou o contrato descobriu isso MEDINDO ANTES de abrir a entrega, e nao depois. Reportou em vez de contornar. A sessao principal conferiu na fonte, e nao no relato dele, e mudou a ordem: a porta subiu na fila e virou a proxima tarefa, encadeada no contrato. Nenhum outro trabalho na celula anda antes dela.\n\nJuntar as duas coisas numa entrega so nao era alternativa: existe uma cerca no projeto que proibe mexer no combinado e na implementacao ao mesmo tempo, justamente para ninguem mudar a promessa e o cumprimento dela na mesma tacada. A ordem era a unica coisa livre para mexer, e ja havia precedente: a mesma inversao aconteceu na fundacao do forum.\n\nNada disso espera por voce, e nada do que esta no ar foi afetado.",
  autoridade: "sessao",
  evidencia: "https://github.com/abundanciabr/sitesdoreino/pull/646 (este PR, que cria a TAR-044). CONFERIDO NA FONTE pela sessao principal: git ls-tree de services/gamificacao em origin/main nao tem config/api.py nem comando de exportacao, e o diff do PR https://github.com/abundanciabr/sitesdoreino/pull/644 muda a linha da celula no ci/manifesto-de-contratos.json de 'not-applicable' para 'required' com exportador ['python','manage.py','export_openapi']. A saida crua do portao, medida pelo robo da TAR-040: \"contrato/gamificacao ERROR exportar contrato vivo de 'gamificacao': exit code 1 / stderr: Unknown command: 'export_openapi'\". O precedente da inversao esta no commit 6b76739 do forum.",
  verificado_em: "2026-08-30",
  precisa_do_dono: false,
  responde_a: null,
  gravidade: "info",
  frente: "comunidade",
  vence_em_dias: null,
  se_eu_nao_decidir: null,
  recomendacao: null,
  reversivel: null,
  impacto: null
});})();
