(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260903-011-corrigi-uma-linha-a-mais-que-eu-tinha-posto-no-contrato",
  tipo: "nota",
  quando: "2026-09-03",
  titulo: "Corrigi uma linha a mais que eu tinha posto no contrato de hoje",
  detalhe: "Erro meu, achado e consertado no mesmo dia, e nada chegou a ficar quebrado para você.\n\nO QUE ACONTECEU: no contrato que entrou hoje de manhã, eu escrevi uma linha dizendo que a porta nova exige senha de máquina. A exigência é correta, mas ela JÁ estava declarada uma vez, no alto do mesmo arquivo, valendo para todas as portas. Repetir criou uma diferença entre o que o contrato dizia e o que o código gera, e o portão que compara os dois reprovou, como deveria.\n\nPOR QUE VOCÊ ESTÁ VENDO ISSO: porque mexer em contrato passa por você nesta casa, mesmo quando é para desfazer um erro meu. É uma linha removida, sem mudança de comportamento nenhuma.\n\nA PORTA CONTINUA PROTEGIDA: o verificador de segurança conferiu as 7 portas dessa parte do sistema, a nova incluída, e todas continuam exigindo senha de máquina. O que saiu foi a repetição, não a proteção.\n\nCOMO EU SEI QUE RESOLVE: eu trouxe o código da porta nova para junto desta correção só para medir, e o portão passou a dizer que o contrato e o código são idênticos, nas 517 linhas comparadas. Depois tirei o código de volta, porque contrato anda em PR sozinho.",
  autoridade: "github",
  evidencia: "PR https://github.com/abundanciabr/sitesdoreino/pull/908, uma linha removida de contracts/notificacoes.openapi.yaml. Medição antes: freeze-de-contrato.sh acusava o diff apenas do bloco security repetido na operação enviarAvisoDeTeste. Medição depois, com o código da célula trazido temporariamente: contrato/notificacoes PASS, idêntico ao congelado, 517 linhas comparadas, e seguranca/notificacoes PASS com 7 operações com autenticação conferida na fonte.",
  verificado_em: "2026-09-03",
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
