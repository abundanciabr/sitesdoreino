function cartaoMpIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    publicKey: JSON.parse(document.getElementById("mp-public-key").textContent),
    totalCents: JSON.parse(document.getElementById("total-cents").textContent),
    status: "carregando",
    pronto: false,
    enviando: false,
    emAnalise: false,
    aprovacaoRecebida: false,
    erro: "",
    cardForm: null,
    proximaConsulta: null,

    async init() {
      await this.poll();
      if (!this.publicKey || !window.MercadoPago) {
        this.erro = "Não foi possível carregar o cartão. Recarregue a página.";
        return;
      }
      try {
        const mp = new MercadoPago(this.publicKey, { locale: "pt-BR" });
        this.cardForm = mp.cardForm({
          amount: (this.totalCents / 100).toFixed(2),
          iframe: true,
          form: {
            id: "mp-form",
            cardNumber: { id: "mp-card-number", placeholder: "Número do cartão" },
            expirationDate: { id: "mp-expiration", placeholder: "MM/AA" },
            securityCode: { id: "mp-security", placeholder: "CVV" },
            cardholderName: { id: "mp-holder-name", placeholder: "Nome impresso no cartão" },
            issuer: { id: "mp-issuer" },
            installments: { id: "mp-installments" },
            identificationType: { id: "mp-document-type" },
            identificationNumber: { id: "mp-holder-cpf", placeholder: "CPF do titular" },
            cardholderEmail: { id: "mp-email" },
          },
          callbacks: {
            onFormMounted: (error) => {
              if (error) this.erro = "Não foi possível carregar os campos do cartão. Recarregue a página.";
            },
            onReady: () => {
              document.getElementById("mp-document-type").value = "CPF";
              this.pronto = true;
            },
            onError: () => {
              this.erro = "Confira os dados do cartão e tente novamente.";
            },
            onSubmit: (event) => { event.preventDefault(); this.confirmar(); },
          },
        });
      } catch (_) {
        this.erro = "Não foi possível iniciar o cartão. Recarregue a página.";
      }
    },

    async confirmar() {
      if (this.enviando || !this.podePagar()) return;
      const dados = this.cardForm.getCardFormData();
      if (!dados.token || !dados.paymentMethodId || dados.identificationType !== "CPF") {
        this.erro = "Confira os dados do cartão e o CPF do titular.";
        return;
      }
      this.enviando = true;
      this.emAnalise = true;
      this.erro = "";
      try {
        const resposta = await api.post(`/pedidos/${this.orderId}/cartao/segunda-opcao`, {
          mp_token: dados.token,
          mp_payment_method_id: dados.paymentMethodId,
          mp_issuer_id: String(dados.issuerId || ""),
          mp_device_id: window.MP_DEVICE_SESSION_ID || "",
          installments: 1,
          holder_name: document.getElementById("mp-holder-name").value.trim(),
          holder_document_number: String(dados.identificationNumber || "").replace(/\D/g, ""),
        });
        this.emAnalise = resposta.payment.status === "pending";
        this.aprovacaoRecebida = resposta.payment.status === "approved";
        if (resposta.payment.status === "rejected") this.erro = "Cartão recusado. Confira os dados ou tente outro cartão.";
        await this.poll();
      } catch (_) {
        await this.poll();
        if (this.podePagar()) this.erro = "Não foi possível concluir. Confira o pedido antes de tentar novamente.";
      } finally {
        this.enviando = false;
      }
    },

    async poll() {
      clearTimeout(this.proximaConsulta);
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
        if (typeof pedido.card_in_review === "boolean") this.emAnalise = pedido.card_in_review;
      } catch (_) {
        this.erro = "Não foi possível consultar agora. Aguarde a próxima consulta.";
      }
      if (this.status === "carregando" || this.status === "aguardando_pagamento") {
        this.proximaConsulta = setTimeout(() => this.poll(), 3000);
      }
    },

    podePagar() {
      return !this.emAnalise && !this.aprovacaoRecebida
        && (this.status === "aguardando_pagamento" || this.status === "recusado");
    },

    statusLabel() {
      if (this.aprovacaoRecebida && this.status === "aguardando_pagamento") return "Pagamento aprovado. Confirmando a compra…";
      if (this.emAnalise) return "Pagamento em análise. Aguarde a confirmação sem pagar novamente.";
      return ({
        carregando: "Consultando o pedido…",
        aguardando_pagamento: "Preencha o cartão para concluir a compra.",
        pago: "Pagamento aprovado!",
        recusado: "Pagamento recusado. Você pode tentar outro cartão.",
        reembolsado: "Pagamento devolvido.",
      })[this.status] || "Consulte o estado do pedido.";
    },

    reais() {
      return (this.totalCents / 100).toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
    },
  };
}
