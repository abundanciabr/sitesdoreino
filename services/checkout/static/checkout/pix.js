// static/checkout/pix.js  [RECEITA:R6 v1] — SÓ Pix. Nada de cartão aqui (INV-P9).
// [INV-P7] Nenhuma transição local para "pago": o único jeito deste arquivo saber
// que o pedido foi pago é o GET /pedidos/{id} responder status="pago".
function pixIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    qr: JSON.parse(document.getElementById("pix-data").textContent) || {},
    status: "aguardando_pagamento",

    async init() {
      await this.poll();
    },

    async poll() {
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status; // [INV-P7] única fonte de status
      } catch (e) {
        // rede falhou nesta rodada; tenta de novo no próximo ciclo
      }
      if (this.status === "aguardando_pagamento") {
        setTimeout(() => this.poll(), 3000);
      }
    },

    statusLabel() {
      return (
        {
          aguardando_pagamento: "Aguardando confirmação do pagamento…",
          pago: "Pagamento confirmado!",
          expirado: "QR Code expirado — gere um novo pedido.",
          recusado: "Pagamento recusado.",
          reembolsado: "Pagamento reembolsado.",
        }[this.status] ?? this.status
      );
    },

    copiar() {
      navigator.clipboard?.writeText(this.qr.qr_code || "");
    },
  };
}
