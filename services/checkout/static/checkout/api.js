// static/checkout/api.js  [RECEITA:R6 v1] — cliente fino; NENHUMA regra de negócio.
// Único arquivo comum entre dados/pix/cartão (doutrina: zero estado compartilhado
// além deste cliente).
const api = {
  _base: "/api/checkout",
  _token() {
    const el = document.getElementById("api-token");
    return el ? JSON.parse(el.textContent) : "";
  },
  _headers(extra) {
    return { ...extra, Authorization: `Bearer ${this._token()}` };
  },
  async get(path) {
    const r = await fetch(`${this._base}${path}`, { headers: this._headers({}) });
    if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(`${this._base}${path}`, {
      method: "POST",
      headers: this._headers({ "Content-Type": "application/json" }),
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${path}: ${r.status}`);
    return r.json();
  },
};
