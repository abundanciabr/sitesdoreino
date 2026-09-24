function cartaoIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    totalCents: JSON.parse(document.getElementById("total-cents").textContent),
    status: "carregando",
    parcelas: [],
    installments: "",
    holderName: "",
    holderDocumentNumber: "",
    appmaxPronto: false,
    carregandoParcelas: false,
    enviando: false,
    erro: "",

    async init() {
      await Promise.all([this.poll(), this.carregarParcelas()]);
      this.iniciarAppmax();
    },

    async poll() {
      this.status = "carregando";
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
      } catch (e) {
        this.status = "erro";
        this.erro = "Não foi possível consultar o pedido. Tente novamente.";
      }
      if (this.status === "aguardando_pagamento") {
        setTimeout(() => this.pollSemTelaTravada(), 3000);
      }
    },

    async pollSemTelaTravada() {
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
      } catch (e) {
        return;
      }
      if (this.status === "aguardando_pagamento") {
        setTimeout(() => this.pollSemTelaTravada(), 3000);
      }
    },

    async carregarParcelas() {
      this.carregandoParcelas = true;
      try {
        const cotacao = await api.get(`/pedidos/${this.orderId}/parcelas`);
        this.parcelas = cotacao.options;
        this.installments = this.parcelas[0]?.installments || "";
      } catch (e) {
        this.erro = "Não foi possível consultar as parcelas. Tente novamente.";
      } finally {
        this.carregandoParcelas = false;
      }
    },

    iniciarAppmax() {
      if (!window.AppmaxScripts?.init) {
        this.erro = "Não foi possível carregar o pagamento com cartão. Recarregue a página.";
        return;
      }
      window.AppmaxScripts.init(
        (dados) => this.confirmarCartao(dados),
        () => {
          this.enviando = false;
          this.erro = "Não foi possível validar o cartão. Confira os dados e tente novamente.";
        },
        this.orderId
      );
      this.appmaxPronto = true;
    },

    async confirmarCartao(dadosTokenizados) {
      if (this.enviando) return;
      this.enviando = true;
      this.erro = "";
      try {
        const resposta = await api.post(`/pedidos/${this.orderId}/cartao`, {
          token: dadosTokenizados.token,
          ...(dadosTokenizados.ip ? { ip: dadosTokenizados.ip } : {}),
          holder_name: this.holderName,
          holder_document_number: this.holderDocumentNumber.replace(/\D/g, ""),
          installments: Number(this.installments),
        });
        this.status = resposta.status;
        if (resposta.payment.status === "rejected") {
          this.erro = "Cartão recusado. Confira os dados ou tente outro cartão.";
        } else {
          this.erro = "Pagamento em análise. A confirmação aparece aqui quando o servidor receber o aviso.";
          await this.pollSemTelaTravada();
        }
      } catch (e) {
        this.erro = "Não foi possível concluir a tentativa. Tente novamente.";
      } finally {
        this.enviando = false;
      }
    },

    statusLabel() {
      return (
        {
          carregando: "Consultando o pedido...",
          aguardando_pagamento: "Aguardando pagamento.",
          pago: "Pagamento aprovado!",
          recusado: "Pagamento recusado. Você pode tentar novamente.",
          reembolsado: "Pagamento reembolsado.",
          erro: "Não foi possível consultar o pedido. Tente consultar novamente.",
        }[this.status] ?? "Estado do pedido desconhecido. Volte à escolha do pagamento."
      );
    },

    podeTentar() {
      return this.status === "aguardando_pagamento" || this.status === "recusado";
    },

    parcelaLabel(opcao) {
      const valor = (opcao.installment_cents / 100).toFixed(2).replace(".", ",");
      return `${opcao.installments}x de R$ ${valor}`;
    },

    botaoLabel() {
      if (!this.appmaxPronto) return "Carregando pagamento";
      if (this.enviando) return "Enviando...";
      return "Pagar com cartão";
    },
  };
}
