// static/checkout/dados.js  [RECEITA:R6 v1] — ilha da página de dados.
// Não sabe nada de Pix nem de cartão além do valor de `method` que o cliente
// escolheu; quem decide o que fazer com isso é o servidor.
function dadosIsland() {
  return {
    offerSlug: JSON.parse(document.getElementById("offer-slug").textContent),
    carregando: true,
    enviando: false,
    erro: "",
    session: null,
    offer: { product_name: "", price_cents: 0, bumps: [] },
    bumpIds: [],
    customer: { name: "", email: "", phone: "" },
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

    async finalizar() {
      this.erro = "";
      this.enviando = true;
      try {
        const pedido = await api.post(`/sessoes/${this.session.id}/pedido`, {
          customer: this.customer,
          bump_ids: this.bumpIds,
          method: this.method,
        });
        const destino = pedido.payment.method === "pix" ? "pix" : "cartao";
        window.location = `/checkout/pedido/${pedido.order_id}/${destino}/`;
      } catch (e) {
        this.erro =
          "Não foi possível concluir o pedido. Confira os dados e tente novamente.";
        this.enviando = false;
      }
    },
  };
}
