(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260927-074-checkout-e-pagamentos-esperam-mandato-para-o-sha256-da-wheel",
  tipo: "pendencia",
  quando: "2026-09-27",
  titulo: "Checkout e pagamentos ainda travam a abertura de sessao; falta sua autorizacao para editar",
  detalhe: "A TAR-833 anotou o codigo de identidade (sha256) do pacote interno de erros em 15 celulas, e a abertura de sessao delas parou de travar. Sobraram checkout e pagamentos: sao as duas celulas de pagamento e cobranca, protegidas por regra da casa que so deixa edita-las com sua autorizacao nominal escrita no pedido. Este pedido nao trouxe essa autorizacao, entao a TAR-837 foi criada e bloqueada em vez de tocar nos dois arquivos.\n\nEnquanto isso, abrir sessao em checkout ou em pagamentos continua travando no mesmo passo que travava nas outras 15 antes desta entrega.",
  autoridade: "sessao",
  evidencia: null,
  verificado_em: null,
  precisa_do_dono: true,
  responde_a: null,
  gravidade: "ambar",
  frente: "fabrica",
  area: "ci",
  vence_em_dias: null,

  porque_so_voce: "Checkout e pagamentos sao as celulas de pagamento e cobranca; a casa exige sua autorizacao nominal, escrita no pedido, antes de qualquer edicao nesses dois caminhos, mesmo para uma anotacao mecanica de sha256.",
  proximo_passo: "Autorize a TAR-837 citando os caminhos services/checkout/requirements.txt e services/pagamentos/requirements.txt, e ela sai da fila bloqueada para a fila de trabalho.",
  se_eu_nao_decidir: "Checkout e pagamentos continuam sem poder abrir sessao de agente pelo caminho oficial; quem precisar trabalhar nessas duas celulas vai travar no mesmo passo do venv.",
  recomendacao: "Autorizar: e a mesma anotacao mecanica ja feita em 15 outras celulas, sem mudar comportamento de cobranca nem senha.",
  reversivel: true,
  impacto: "baixo",

  portao: null
});})();
