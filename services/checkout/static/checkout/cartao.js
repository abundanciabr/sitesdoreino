const CONSULTA_INDISPONIVEL = "Não conseguimos consultar agora. Vamos tentar de novo em instantes.";

function cartaoIsland() {
  return {
    orderId: JSON.parse(document.getElementById("order-id").textContent),
    externalId: JSON.parse(document.getElementById("appmax-external-id").textContent),
    mpPublicKey: JSON.parse(document.getElementById("mp-public-key").textContent),
    totalCents: JSON.parse(document.getElementById("total-cents").textContent),
    status: "carregando",
    parcelas: [],
    installments: "",
    holderName: "",
    holderDocumentNumber: "",
    appmaxPronto: false,
    ip: "",
    carregandoParcelas: false,
    enviando: false,
    emAnalise: false,
    erro: "",
    proximaConsulta: null,
    mpTokenizacao: null,
    mpDados: null,
    segundaOpcaoEnviada: false,
    segundaOpcaoPendente: false,

    async init() {
      await Promise.all([this.poll(), this.carregarParcelas()]);
      const form = document.querySelector("form[data-appmax-checkout]");
      form?.addEventListener("click", (event) => {
        if (event.target.closest("button[type=submit]")) this.prepararMp();
      }, true);
      form?.addEventListener("submit", () => this.prepararMp(), true);
      this.iniciarAppmax();
    },

    async poll() {
      this.status = "carregando";
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
        if (this.status === "recusado" && !pedido.card_second_option_until) this.segundaOpcaoEnviada = false;
        this.emAnalise = pedido.card_in_review === true;
        if (pedido.card_second_option_until) await this.enviarSegundaOpcao();
      } catch (e) {
        this.status = "erro";
        this.erro = "Não foi possível consultar o pedido. Tente novamente.";
      }
      this.agendarConsulta();
    },

    async pollSemTelaTravada() {
      try {
        const pedido = await api.get(`/pedidos/${this.orderId}`);
        this.status = pedido.status;
        if (this.status === "recusado" && !pedido.card_second_option_until) this.segundaOpcaoEnviada = false;
        if (pedido.card_second_option_until) {
          this.emAnalise = false;
          await this.enviarSegundaOpcao();
        } else {
        // Cartão aprovado sem aviso ainda não está no provedor, mas o pedido
        // também não está pago: a análise vista nesta aba segue até o aviso.
        this.emAnalise =
          pedido.card_in_review === true || (this.emAnalise && this.status === "aguardando_pagamento");
        if (!this.enviando && (this.emAnalise || this.status !== "aguardando_pagamento")) this.descartarMp();
        }
        if (this.erro === CONSULTA_INDISPONIVEL) this.erro = "";
      } catch (e) {
        if (this.aguardandoResultado()) this.erro = CONSULTA_INDISPONIVEL;
      }
      this.agendarConsulta();
    },

    aguardandoResultado() {
      return this.status === "aguardando_pagamento" || this.emAnalise || this.segundaOpcaoPendente;
    },

    agendarConsulta() {
      clearTimeout(this.proximaConsulta);
      if (this.aguardandoResultado()) {
        this.proximaConsulta = setTimeout(() => this.pollSemTelaTravada(), 3000);
      }
    },

    async carregarParcelas() {
      this.carregandoParcelas = true;
      try {
        const cotacao = await api.get(`/pedidos/${this.orderId}/parcelas`);
        this.parcelas = cotacao.options;
        let sugerida = null;
        try { sugerida = JSON.parse(document.getElementById("parcelas-sugeridas")?.textContent || "null"); } catch (_) {}
        const marcada = this.parcelas.find((opcao) => opcao.installments === sugerida);
        this.installments = (marcada || this.parcelas[0])?.installments || "";
      } catch (e) {
        this.erro = "Não foi possível consultar as parcelas. Tente novamente.";
      } finally {
        this.carregandoParcelas = false;
      }
    },

    iniciarAppmax() {
      if (!this.externalId) {
        this.erro = "A instalação da Appmax está incompleta. Avise a loja para configurar o pagamento.";
        return;
      }
      if (!window.AppmaxScripts?.init) {
        this.erro = "Não foi possível carregar o pagamento com cartão. Recarregue a página.";
        return;
      }
      window.AppmaxScripts.init({
        externalId: this.externalId,
        onIp: ({ ip }) => {
          this.ip = ip;
          this.appmaxPronto = true;
        },
        onTokenize: ({ token }) => this.confirmarCartao(token),
        onError: (falha) => {
          this.enviando = false;
          if (falha.stage === "ip") {
            this.erro = "Não foi possível identificar esta conexão. Recarregue a página e tente novamente.";
          } else if (falha.stage === "tokenize") {
            this.erro = "Não foi possível validar o cartão. Confira os dados e tente novamente.";
          } else if (falha.stage === "setup") {
            this.erro = "Não foi possível iniciar o pagamento. Recarregue a página e tente novamente.";
          }
        },
      });
    },

    prepararMp() {
      this.segundaOpcaoEnviada = false;
      this.mpDados = null;
      this.mpTokenizacao = null;
      if (!this.mpPublicKey || !window.MercadoPago) return;
      const campo = (nome) => document.querySelector(`[appmax-form-element="${nome}"]`)?.value?.trim() || "";
      const numero = campo("number").replace(/\D/g, "");
      const documento = this.holderDocumentNumber.replace(/\D/g, "");
      let ano = campo("expiration_year");
      if (/^\d{2}$/.test(ano)) ano = `20${ano}`;
      if (!numero || !documento || !/^\d{4}$/.test(ano)) return;
      const dados = {
        cardNumber: numero,
        cardholderName: this.holderName,
        cardExpirationMonth: campo("expiration_month"),
        cardExpirationYear: ano,
        securityCode: campo("cvv"),
        identificationType: documento.length === 14 ? "CNPJ" : "CPF",
        identificationNumber: documento,
      };
      try {
        const mp = new MercadoPago(this.mpPublicKey, { locale: "pt-BR" });
        const trabalho = Promise.all([
          mp.createCardToken(dados),
          mp.getPaymentMethods({ bin: numero.slice(0, 8) }),
        ]).then(([token, metodos]) => {
          const metodo = metodos?.results?.find((item) => item.payment_type_id === "credit_card") || metodos?.results?.[0];
          if (!token?.id || !metodo?.id) return null;
          return {
            mp_token: token.id,
            mp_payment_method_id: metodo.id,
            mp_issuer_id: String(metodo.issuer?.id || ""),
            mp_device_id: window.MP_DEVICE_SESSION_ID || "",
            installments: Number(this.installments),
            holder_name: this.holderName,
            holder_document_number: documento,
          };
        }).catch(() => null);
        this.mpTokenizacao = Promise.race([
          trabalho,
          new Promise((resolve) => setTimeout(() => resolve(null), 5000)),
        ]);
      } catch (_) { this.mpTokenizacao = null; }
    },

    descartarMp() {
      this.mpDados = null;
      this.mpTokenizacao = null;
    },

    async enviarSegundaOpcao() {
      if (this.segundaOpcaoEnviada) return;
      this.segundaOpcaoEnviada = true;
      this.segundaOpcaoPendente = true;
      try {
        if (!this.mpDados && this.mpTokenizacao) this.mpDados = await this.mpTokenizacao;
        if (!this.mpDados) {
          this.erro = "Não foi possível concluir a tentativa. Consulte o pedido em instantes.";
          return;
        }
        const resposta = await api.post(`/pedidos/${this.orderId}/cartao/segunda-opcao`, this.mpDados);
        if (resposta.payment?.status === "rejected") this.erro = "Cartão recusado. Confira os dados ou tente outro cartão.";
        else this.emAnalise = resposta.status === "aguardando_pagamento";
      } catch (_) {
        this.erro = "Não foi possível concluir a tentativa. Consulte o pedido em instantes.";
      } finally {
        this.segundaOpcaoPendente = false;
        this.descartarMp();
      }
    },

    async confirmarCartao(token) {
      if (this.enviando) return;
      this.enviando = true;
      this.erro = "";
      try {
        if (this.mpTokenizacao) this.mpDados = await this.mpTokenizacao;
        const resposta = await api.post(`/pedidos/${this.orderId}/cartao`, {
          token,
          ip: this.ip,
          holder_name: this.holderName,
          holder_document_number: this.holderDocumentNumber.replace(/\D/g, ""),
          installments: Number(this.installments),
          ...(this.mpDados ? { mp_pronto: true } : {}),
        });
        this.status = resposta.status;
        if (resposta.payment.status === "segunda_opcao") {
          await this.enviarSegundaOpcao();
          await this.pollSemTelaTravada();
        } else if (resposta.payment.status === "rejected") {
          this.erro = "Cartão recusado. Confira os dados ou tente outro cartão.";
          this.descartarMp();
        } else {
          this.emAnalise = this.status === "aguardando_pagamento";
          this.descartarMp();
          await this.pollSemTelaTravada();
        }
      } catch (e) {
        // A aba antiga que tenta de novo leva 409 enquanto a tentativa anterior
        // está no provedor: relê o pedido e mostra a análise em vez de pedir
        // outra tentativa.
        await this.pollSemTelaTravada();
        if (this.podeTentar()) {
          this.erro = "Não foi possível concluir a tentativa. Tente novamente.";
        }
      } finally {
        this.enviando = false;
      }
    },

    statusLabel() {
      if (this.segundaOpcaoPendente) return "Concluindo pagamento...";
      if (this.emAnalise) {
        return "Pagamento em análise. Não é preciso pagar de novo. A confirmação aparece aqui assim que a análise terminar.";
      }
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
      if (this.emAnalise || this.segundaOpcaoPendente || this.segundaOpcaoEnviada) return false;
      return this.status === "aguardando_pagamento" || this.status === "recusado";
    },

    reais(centavos) {
      const valor = (centavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return `R$ ${valor}`;
    },

    parcelaLabel(opcao) {
      return `${opcao.installments}x de ${this.reais(opcao.installment_cents)}`;
    },

    botaoLabel() {
      if (!this.appmaxPronto) return "Carregando pagamento";
      if (this.enviando) return "Enviando...";
      return "Pagar com cartão";
    },
  };
}
