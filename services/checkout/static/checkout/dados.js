// static/checkout/dados.js  [RECEITA:R6 v1] — ilha da página de dados.
// Não sabe nada de Pix nem de cartão além do valor de `method` que o cliente
// escolheu; quem decide o que fazer com isso é o servidor.
function dadosIsland() {
  const cpfValido = (valor) => {
    const cpf = String(valor || "").replace(/\D/g, "");
    if (cpf.length !== 11 || /^(\d)\1+$/.test(cpf)) return false;
    for (const tamanho of [9, 10]) {
      const soma = [...cpf.slice(0, tamanho)].reduce((total, digito, indice) => total + Number(digito) * (tamanho + 1 - indice), 0);
      const verificador = (soma * 10) % 11;
      if ((verificador === 10 ? 0 : verificador) !== Number(cpf[tamanho])) return false;
    }
    return true;
  };
  return {
    offerSlug: JSON.parse(document.getElementById("offer-slug").textContent),
    atribuicao: JSON.parse(document.getElementById("atribuicao").textContent),
    appmaxPix: JSON.parse(document.getElementById("appmax-pix-enabled").textContent),
    appmaxCard: JSON.parse(document.getElementById("appmax-card-enabled").textContent),
    carregando: true,
    enviando: false,
    erro: "",
    linkUsado: "",
    pedidoAberto: "",
    enviosQuePodemTerCriado: [],
    session: null,
    offer: { product_name: "", price_cents: 0, bumps: [] },
    bumpIds: [],
    customer: { name: "", email: "", phone: "", cpf: "" },
    cpfMascarado: "",
    usarCpfAnterior: false,
    trocandoCpf: false,
    method: "pix",
    appmaxIp: "",

    // Relativo de proposito: esta pagina vive em <prefixo>/checkout/<slug>/, e o
    // destino em <prefixo>/checkout/pedido/... — um caminho absoluto hardcoded
    // perderia o prefixo do gateway (SCRIPT_NAME=/checkout).
    irParaPedido(orderId, metodo) {
      window.location = `../pedido/${orderId}/${metodo === "pix" ? "pix" : "cartao"}/`;
    },

    async init() {
      let seguindoParaOPedido = false;
      if (this.appmaxPix && window.AppmaxScripts?.init) {
        try {
          window.AppmaxScripts.init({
            externalId: JSON.parse(document.getElementById("appmax-external-id").textContent),
            onIp: ({ ip }) => { this.appmaxIp = ip || ""; },
            onError: () => {},
          });
        } catch (_) { /* O IP do servidor continua disponível. */ }
      }
      try {
        let anteriores = {};
        try { anteriores = JSON.parse(localStorage.getItem("checkout-comprador") || "{}"); } catch (_) {}
        const consulta = new URLSearchParams(window.location.search);
        const leadId = consulta.get("lead") || "";
        const link = consulta.get("link") || "";
        this.session = await api.post("/sessoes", {
          offer_slug: this.offerSlug, utm: this.atribuicao, lead_id: leadId,
          email_para_cpf: anteriores.email || "",
          ...(link ? { link } : {}),
        });
        // O link de compra serve um pedido por vez: se ele já virou pedido e o
        // pedido segue valendo, a pessoa vai para a página dele, em vez de ver
        // o formulário e esbarrar num erro ao enviar.
        if (this.session.pedido_existente) {
          // O número do pedido só vem enquanto falta pagar. Pedido já pago ou
          // devolvido chega sem ele, e a página só avisa que o link foi usado.
          if (!this.session.pedido_existente.order_id) {
            this.linkUsado = "Este link já foi usado e o pagamento dele já está registrado.";
            return;
          }
          seguindoParaOPedido = true;
          this.irParaPedido(this.session.pedido_existente.order_id, this.session.pedido_existente.method);
          return;
        }
        const metodoDoLink = this.session.condicao?.metodo;
        if (metodoDoLink === "pix" || (metodoDoLink === "card" && this.appmaxCard)) this.method = metodoDoLink;
        this.offer = this.session.offer;
        for (const campo of ["name", "email", "phone"]) {
          if (!this.customer[campo]) this.customer[campo] = this.session.prefill?.[campo] || anteriores[campo] || "";
        }
        this.cpfMascarado = this.session.cpf_mascarado || "";
        this.usarCpfAnterior = Boolean(this.cpfMascarado);
      } catch (e) {
        this.erro = "Não foi possível carregar esta oferta.";
      } finally {
        if (!seguindoParaOPedido) this.carregando = false;
      }
    },

    alternarBump(id) {
      const i = this.bumpIds.indexOf(id);
      if (i === -1) this.bumpIds.push(id);
      else this.bumpIds.splice(i, 1);
    },

    reais(centavos) {
      const valor = (centavos / 100).toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
      return `R$ ${valor}`;
    },

    totalCents() {
      const principal = this.offer.price_cents || 0;
      const bumps = (this.offer.bumps || [])
        .filter((b) => this.bumpIds.includes(b.id))
        .reduce((soma, b) => soma + b.price_cents, 0);
      return principal + bumps;
    },

    async referenciaDiagnostico() {
      const bytes = new TextEncoder().encode(this.session.id);
      const digest = await crypto.subtle.digest("SHA-256", bytes);
      return Array.from(new Uint8Array(digest), (byte) =>
        byte.toString(16).padStart(2, "0"),
      ).join("");
    },

    async finalizar() {
      this.erro = "";
      this.pedidoAberto = "";
      const telefone = this.customer.phone.replace(/\D/g, "");
      if (this.customer.name.trim().split(/\s+/).length < 2 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.customer.email.trim()) || ![10, 11].includes(telefone.length) || (!this.usarCpfAnterior && !cpfValido(this.customer.cpf))) {
        this.erro = "Informe nome completo, e-mail, telefone com DDD e CPF válido.";
        return;
      }
      this.enviando = true;
      const corpo = {
        customer: { ...this.customer, phone: telefone, cpf: this.usarCpfAnterior ? "" : this.customer.cpf.replace(/\D/g, "") },
        usar_cpf_anterior: this.usarCpfAnterior,
        bump_ids: this.bumpIds,
        method: this.method,
        ...(this.appmaxPix && this.method === "pix" && this.appmaxIp ? { ip: this.appmaxIp } : {}),
        ...(this.method === "pix" && typeof window.MP_DEVICE_SESSION_ID === "string" && window.MP_DEVICE_SESSION_ID
          ? { mp_device_id: window.MP_DEVICE_SESSION_ID } : {}),
      };
      // O que define a compra (o IP fica de fora: pode chegar depois do 1º clique).
      const envio = JSON.stringify([corpo.customer, corpo.usar_cpf_anterior, [...corpo.bump_ids].sort(), corpo.method]);
      try {
        let pedido;
        try {
          pedido = await api.post(`/sessoes/${this.session.id}/pedido`, corpo);
          this.enviosQuePodemTerCriado = [envio];
        } catch (e) {
          if (!(e.status === 409 && e.corpo?.order_id && e.corpo?.payment)) {
            // Sem resposta ou erro fora de 4xx/502: o pedido pode ter nascido
            // deste envio (a resposta se perdeu).
            const semPedido = e.status === 502 || (e.status >= 400 && e.status < 500);
            if (!semPedido && !this.enviosQuePodemTerCriado.includes(envio)) this.enviosQuePodemTerCriado.push(envio);
            throw e;
          }
          // 409: esta sessão já tem pedido. Segue calado para ele quando nenhum
          // envio desta página pode tê-lo criado (o pedido é de antes: link
          // reaberto, outra aba) ou quando só um pode ter criado e é igual ao
          // atual (a resposta do clique anterior se perdeu). Se algum envio
          // desta página pode ter criado o pedido com dados diferentes dos
          // atuais (outra forma de pagamento, outro e-mail, outro bump ou outro
          // comprador), o pedido que existe não é o que está na tela: avisa e
          // oferece o link, sem levar para lá calado.
          pedido = e.corpo;
          const podemTerCriado = this.enviosQuePodemTerCriado;
          const segueCalado = podemTerCriado.length === 0 || (podemTerCriado.length === 1 && podemTerCriado[0] === envio);
          if (!segueCalado) {
            const destinoAberto = pedido.payment.method === "pix" ? "pix" : "cartao";
            this.pedidoAberto = `../pedido/${pedido.order_id}/${destinoAberto}/`;
            this.erro = `Seu pedido anterior, por ${pedido.payment.method === "pix" ? "Pix" : "cartão"}, continua aberto. Continue por ele ou recarregue a página para começar outra compra.`;
            this.enviando = false;
            return;
          }
        }
        try { localStorage.setItem("checkout-comprador", JSON.stringify({ name: this.customer.name, email: this.customer.email, phone: telefone })); } catch (_) {}
        this.irParaPedido(pedido.order_id, pedido.payment.method);
      } catch (e) {
        this.erro = "Não foi possível concluir o pedido. Confira os dados e tente novamente.";
        if (this.appmaxPix && this.method === "pix") {
          this.erro = "Não foi possível concluir o pedido. Não reenvie esta compra.";
          try {
            const referencia = await this.referenciaDiagnostico();
            this.erro += ` Referência: ${referencia}`;
          } catch (_) {}
        }
        this.enviando = false;
      }
    },
  };
}
