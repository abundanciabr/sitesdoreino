function cartaoIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    totalCents: JSON.parse(document.getElementById("total-cents").textContent),
    status: "carregando",

    async init() {
      await this.poll();
    },

    async poll() {
      this.status = "carregando";
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
      } catch (e) {
        this.status = "erro";
      }
    },

    statusLabel() {
      return (
        {
          carregando: "Consultando o pedido...",
          aguardando_pagamento: "Pagamento com cartão indisponível.",
          pago: "Pagamento aprovado!",
          recusado: "Pagamento recusado. Volte à escolha do pagamento.",
          reembolsado: "Pagamento reembolsado.",
          erro: "Não foi possível consultar o pedido. Tente consultar novamente.",
        }[this.status] ?? "Estado do pedido desconhecido. Volte à escolha do pagamento."
      );
    },
  };
}
