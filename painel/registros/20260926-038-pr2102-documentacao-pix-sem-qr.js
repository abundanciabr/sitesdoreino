(function(){ (window.REGISTROS = window.REGISTROS || []).push({
  arquivo: "20260926-038-pr2102-documentacao-pix-sem-qr",
  tipo: "resposta",
  quando: "2026-09-26",
  titulo: "PR 2102: a consulta do pedido não documenta o QR",
  detalhe: "Complemento ao 035. A aba Pix da consulta GET /v1/orders/{order_id} documenta end_to_end_id, pay_reference, creation_date e expiration_date; seu exemplo não documenta QR nem copia-e-cola. O POST de pagamento documenta pix_qrcode e pix_emv, mas isso não prova QR existente, não explica o 400 nem falha externa. Falta fonte oficial para recuperar QR sem novo POST.",
  autoridade: "sessao",
  evidencia: "https://docs.appmax.com.br/api-reference/orders/consultar-pedido https://docs.appmax.com.br/api-reference/payments/pix TEMP/tar736-provas-finais/schema-get-pix-oficial.json",
  verificado_em: "2026-09-26",
  precisa_do_dono: false,
  responde_a: "20260926-035-pr2102-leitura-qr-nao-comprovada",
  gravidade: "ambar",
  area: "painel",
  tarefa: "TAR-736"
});})();
