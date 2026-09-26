(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260926-038-pr2102-documentacao-pix-sem-qr",
  tipo: "resposta",
  quando: "2026-09-26",
  titulo: "PR 2102: o manual do Pix não documenta o QR",
  detalhe: "Complemento ao registro 20260926-035. A aba Pix do GET /v1/orders/{order_id} documenta end_to_end_id, pay_reference, creation_date e expiration_date; o exemplo oficial não documenta QR nem copia-e-cola. Isso limita a leitura atual e não explica o 400 ou falha externa. Falta fonte oficial para recuperar QR existente sem novo POST.",
  autoridade: "sessao",
  evidencia: "https://docs.appmax.com.br/api-reference/orders/consultar-pedido TEMP/tar736-provas-finais/schema-get-pix-oficial.json",
  verificado_em: "2026-09-26",
  precisa_do_dono: false,
  responde_a: "20260926-035-pr2102-leitura-qr-nao-comprovada",
  gravidade: "ambar",
  area: "painel",
  tarefa: "TAR-736"
});})();
