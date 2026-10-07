const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const test = require("node:test");
const source = fs.readFileSync(path.join(__dirname, "../static/checkout/cartao_mp.js"), "utf8");

function page(api) {
  const fields = {
    "order-id": { textContent: '"pedido-simulado"' },
    "mp-public-key": { textContent: '"APP_USR-simulado"' },
    "total-cents": { textContent: "990" },
    "mp-holder-name": { value: "Titular de Teste" },
    "mp-document-type": { value: "" },
  };
  let setup, sdk;
  class SecureCardForm {
    #data = { token: "token-simulado", paymentMethodId: "visa", identificationType: "CPF", identificationNumber: "52998224725" };
    getCardFormData() { return this.#data; }
  }
  const context = {
    document: { getElementById: (id) => fields[id] }, window: {}, api,
    setTimeout: () => 1, clearTimeout: () => {},
    MercadoPago: function () {
      this.cardForm = (options) => {
        setup = options;
        options.callbacks.onReady();
        sdk = new SecureCardForm();
        return sdk;
      };
    },
  };
  context.window.MercadoPago = context.MercadoPago;
  vm.createContext(context);
  vm.runInContext(source, context);
  const island = new Proxy(context.cartaoMpIsland(), {
    get(target, key) {
      const value = Reflect.get(target, key);
      return value && typeof value === "object" ? new Proxy(value, {}) : value;
    },
  });
  return { island, setup: () => setup, sdk: () => sdk };
}

test("SDK protege os campos e o servidor recebe somente token e identificação", async () => {
  let sent;
  const p = page({
    get: async () => ({ status: "aguardando_pagamento", card_in_review: false }),
    post: async (_, body) => { sent = body; return { payment: { status: "approved" } }; },
  });
  await p.island.init();
  assert.equal(p.setup().iframe, true);
  await p.island.confirmar();
  assert.equal(sent.installments, 1);
  assert.equal(sent.mp_token, "token-simulado");
  assert.equal("cardNumber" in sent || "securityCode" in sent || "total_cents" in sent, false);
  assert.equal(p.island.podePagar(), false);
});

test("resposta incerta mantém a análise quando a consulta não confirma o estado", async () => {
  let calls = 0;
  const p = page({
    get: async () => ({ status: "aguardando_pagamento", ...(calls === 0 ? { card_in_review: false } : {}) }),
    post: async () => { calls++; throw Error("timeout simulado"); },
  });
  await p.island.init();
  await p.island.confirmar();
  await p.island.confirmar();
  assert.equal(calls, 1);
  assert.equal(p.island.emAnalise, true);
  assert.equal(p.island.podePagar(), false);
});

test("recusa confirmada permite tentar outro cartão", async () => {
  const p = page({
    get: async () => ({ status: "recusado", card_in_review: false }),
    post: async () => ({ payment: { status: "rejected" } }),
  });
  await p.island.init();
  await p.island.confirmar();
  assert.equal(p.island.podePagar(), true);
});

test("erro na leitura segura do SDK mostra retorno sem enviar cobrança", async () => {
  let sent = 0;
  const p = page({ get: async () => ({ status: "aguardando_pagamento" }), post: async () => { sent++; } });
  await p.island.init();
  p.sdk().getCardFormData = () => { throw Error("erro simulado"); };
  await p.island.confirmar();
  assert.equal(sent, 0);
  assert.match(p.island.erro, /ler o cartão com segurança/);
  assert.equal(p.island.podePagar(), true);
});

test("tokenização pendente e inválida têm retorno visível sem iniciar cobrança", async () => {
  let sent = 0;
  const p = page({ get: async () => ({ status: "aguardando_pagamento" }), post: async () => { sent++; } });
  await p.island.init();
  const end = p.setup().callbacks.onFetching("cardToken");
  assert.equal(p.island.verificando, true);
  p.setup().callbacks.onCardTokenReceived([{ message: "dado privado simulado" }]);
  assert.equal(p.island.verificando, false);
  assert.match(p.island.erro, /não foi enviado para cobrança/);
  assert.doesNotMatch(p.island.erro, /dado privado/);
  end();
  assert.equal(p.island.emAnalise, false);
  assert.equal(sent, 0);
});

test("campos obrigatórios e validação do iframe informam o campo sem expor valores", async () => {
  const p = page({ get: async () => ({ status: "aguardando_pagamento" }) });
  await p.island.init();
  p.island.campoObrigatorio({ target: { id: "mp-holder-cpf" } });
  assert.match(p.island.erro, /CPF do titular/);
  p.setup().callbacks.onValidityChange([{ message: "dado privado simulado" }], "cardNumber");
  assert.equal(p.island.erro, "Confira o número do cartão.");
});
