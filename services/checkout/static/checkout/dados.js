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
    session: null,
    offer: { product_name: "", price_cents: 0, bumps: [] },
    bumpIds: [],
    customer: { name: "", email: "", phone: "", cpf: "" },
    cpfMascarado: "",
    usarCpfAnterior: false,
    trocandoCpf: false,
    method: "pix",
    appmaxIp: "",

    async init() {
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
        const leadId = new URLSearchParams(window.location.search).get("lead") || "";
        this.session = await api.post("/sessoes", {
          offer_slug: this.offerSlug, utm: this.atribuicao, lead_id: leadId,
          email_para_cpf: anteriores.email || "",
        });
        this.offer = this.session.offer;
        for (const campo of ["name", "email", "phone"]) {
          if (!this.customer[campo]) this.customer[campo] = this.session.prefill?.[campo] || anteriores[campo] || "";
        }
        this.cpfMascarado = this.session.cpf_mascarado || "";
        this.usarCpfAnterior = Boolean(this.cpfMascarado);
      } catch (e) {
        this.erro = "Não foi possível carregar esta oferta.";
      } finally {
        this.carregando = false;
      }
    },

    alternarBump(id) {
      const i = this.bumpIds.indexOf(id);
      if (i === -1) this.bumpIds.push(id);
      else this.bumpIds.splice(i, 1);
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
      const telefone = this.customer.phone.replace(/\D/g, "");
      if (this.customer.name.trim().split(/\s+/).length < 2 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(this.customer.email.trim()) || ![10, 11].includes(telefone.length) || (!this.usarCpfAnterior && !cpfValido(this.customer.cpf))) {
        this.erro = "Informe nome completo, e-mail, telefone com DDD e CPF válido.";
        return;
      }
      this.enviando = true;
      try {
        const pedido = await api.post(`/sessoes/${this.session.id}/pedido`, {
          customer: { ...this.customer, phone: telefone, cpf: this.usarCpfAnterior ? "" : this.customer.cpf.replace(/\D/g, "") },
          usar_cpf_anterior: this.usarCpfAnterior,
          bump_ids: this.bumpIds,
          method: this.method,
          ...(this.appmaxPix && this.method === "pix" && this.appmaxIp ? { ip: this.appmaxIp } : {}),
        });
        const destino = pedido.payment.method === "pix" ? "pix" : "cartao";
        try { localStorage.setItem("checkout-comprador", JSON.stringify({ name: this.customer.name, email: this.customer.email, phone: telefone })); } catch (_) {}
        // Relativo de proposito: esta pagina vive em <prefixo>/checkout/<slug>/,
        // e o destino em <prefixo>/checkout/pedido/... — um caminho absoluto
        // hardcoded perderia o prefixo do gateway (SCRIPT_NAME=/checkout).
        window.location = `../pedido/${pedido.order_id}/${destino}/`;
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
