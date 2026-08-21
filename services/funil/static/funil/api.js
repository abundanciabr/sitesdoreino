// static/funil/api.js  # [RECEITA:R6 v1] — cliente fino; NENHUMA regra de negócio
const api = {
  async post(path, body) {
    const r = await fetch(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${path}: ${r.status}`);
    return r.json();
  },
};
