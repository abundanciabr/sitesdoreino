// static/checkout/cartao.js  [RECEITA:R6 v1] — SÓ cartão. Nada de Pix aqui (INV-P9).
// [INV-P7] Nenhuma transição local para "pago": o único jeito deste arquivo saber
// que o pedido foi aprovado é o GET /pedidos/{id} responder status="pago".
// O mount do Card Payment Brick do MP entra aqui numa sessão futura (esqueleto
// funcional por ora — fora do escopo deste despacho).
function cartaoIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    totalCents: JSON.parse(document.getElementById("total-cents").textContent),
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
          pago: "Pagamento aprovado!",
          recusado: "Pagamento recusado — tente outro cartão.",
          reembolsado: "Pagamento reembolsado.",
        }[this.status] ?? this.status
      );
    },
  };
}
