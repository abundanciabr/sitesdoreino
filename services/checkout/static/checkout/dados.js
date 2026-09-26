// static/checkout/dados.js  [RECEITA:R6 v1] — ilha da página de dados.
// Não sabe nada de Pix nem de cartão além do valor de `method` que o cliente
// escolheu; quem decide o que fazer com isso é o servidor.
function dadosIsland() {
  return {
    offerSlug: JSON.parse(document.getElementById("offer-slug").textContent),
    appmaxPix: JSON.parse(document.getElementById("appmax-pix-enabled").textContent),
    appmaxCard: JSON.parse(document.getElementById("appmax-card-enabled").textContent),
    carregando: true,
    enviando: false,
    erro: "",
    session: null,
    offer: { product_name: "", price_cents: 0, bumps: [] },
    bumpIds: [],
    customer: { name: "", email: "", phone: "", cpf: "" },
    method: "pix",

    async init() {
      try {
        this.session = await api.post("/sessoes", { offer_slug: this.offerSlug });
        this.offer = this.session.offer;
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
      if (this.appmaxPix && this.method === "pix") {
        const telefone = this.customer.phone.replace(/\D/g, "");
        const cpf = this.customer.cpf.replace(/\D/g, "");
        if (this.customer.name.trim().split(/\s+/).length < 2 || ![10, 11].includes(telefone.length) || cpf.length !== 11) {
          this.erro = "Informe nome completo, telefone com DDD e CPF com 11 dígitos para pagar por Pix.";
          return;
        }
      }
      this.enviando = true;
      try {
        const pedido = await api.post(`/sessoes/${this.session.id}/pedido`, {
          customer: this.customer,
          bump_ids: this.bumpIds,
          method: this.method,
        });
        const destino = pedido.payment.method === "pix" ? "pix" : "cartao";
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
