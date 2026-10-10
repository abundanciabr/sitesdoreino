(() => {
  'use strict';
  const el = id => document.getElementById(id);
  const config = JSON.parse(el('checkout-config').textContent);
  const digits = value => String(value || '').replace(/\D/g, '');
  const money = cents => (Number(cents) / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
  const state = { sessionId: '', orderId: '', orderMethod: '', orderBaseTotal: 0, quote: null, appmaxReady: false, ip: '', busy: false, pending: false, uncertain: false, polling: null, tokenizeTimer: null, tokenizing: false, submitAuthorized: false };
  const storageKey = `checkout-appmax-order:${config.offerSlug}${config.environment === 'sandbox' ? ':sandbox' : ''}`;
  const formIds = ['buyer-email', 'buyer-email-confirm', 'buyer-name', 'buyer-cpf', 'buyer-phone'];
  const cardIds = ['card-number', 'card-expiry', 'card-cvv', 'card-holder', 'card-holder-cpf'];

  async function request(path, options = {}) {
    const response = await fetch(`${config.apiBase}${path}`, {
      ...options,
      headers: { Authorization: `Bearer ${config.apiToken}`, ...(options.body ? { 'Content-Type': 'application/json' } : {}) },
      cache: 'no-store',
    });
    let body = null;
    try { body = await response.json(); } catch (_) { /* A resposta pode estar vazia. */ }
    if (!response.ok) {
      const error = new Error('A solicitação não pôde ser concluída.');
      error.status = response.status;
      error.body = body;
      throw error;
    }
    return body;
  }
  const get = path => request(path);
  const post = (path, body) => request(path, { method: 'POST', body: JSON.stringify(body) });
  function status(message, type = 'info') {
    const box = el('checkout-status');
    box.textContent = message;
    box.dataset.state = type;
    box.hidden = !message;
  }
  function fieldError(id, message) {
    el(`${id}-error`).textContent = message;
    el(id).setAttribute('aria-invalid', String(Boolean(message)));
    return !message;
  }
  function cpfValid(value) {
    const cpf = digits(value);
    if (!/^\d{11}$/.test(cpf) || /^(\d)\1+$/.test(cpf)) return false;
    for (const length of [9, 10]) {
      const sum = [...cpf.slice(0, length)].reduce((total, digit, index) => total + Number(digit) * (length + 1 - index), 0);
      const check = (sum * 10) % 11;
      if ((check === 10 ? 0 : check) !== Number(cpf[length])) return false;
    }
    return true;
  }
  function cardValid(value) {
    const number = digits(value);
    if (!/^\d{13,19}$/.test(number) || /^(\d)\1+$/.test(number)) return false;
    let sum = 0;
    [...number].reverse().forEach((digit, index) => {
      let item = Number(digit);
      if (index % 2) { item *= 2; if (item > 9) item -= 9; }
      sum += item;
    });
    return sum % 10 === 0;
  }
  function expiryValid(value) {
    if (!/^\d{2}\/\d{2}$/.test(value)) return false;
    const [month, year] = value.split('/').map(Number);
    const now = new Date();
    const fullYear = 2000 + year;
    return month >= 1 && month <= 12 && (fullYear > now.getFullYear() || (fullYear === now.getFullYear() && month >= now.getMonth() + 1));
  }
  function validate(id) {
    const value = el(id).value.trim();
    let error = '';
    switch (id) {
      case 'buyer-email': error = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value) ? '' : 'Digite um e-mail válido.'; break;
      case 'buyer-email-confirm': error = value && value.toLowerCase() === el('buyer-email').value.trim().toLowerCase() ? '' : 'Os dois e-mails precisam ser iguais.'; break;
      case 'buyer-name': error = value.split(/\s+/).length >= 2 ? '' : 'Digite seu nome completo.'; break;
      case 'buyer-cpf': error = cpfValid(value) ? '' : 'Digite um CPF válido.'; break;
      case 'buyer-phone': error = /^\d{10,11}$/.test(digits(value)) ? '' : 'Digite seu celular com DDD.'; break;
      case 'card-number': error = cardValid(value) ? '' : 'Confira o número do cartão.'; break;
      case 'card-expiry': error = expiryValid(value) ? '' : 'Informe a validade em MM/AA.'; break;
      case 'card-cvv': error = /^\d{3,4}$/.test(digits(value)) ? '' : 'Informe os 3 ou 4 dígitos do CVV.'; break;
      case 'card-holder': error = value.split(/\s+/).length >= 2 ? '' : 'Digite o nome completo do titular.'; break;
      case 'card-holder-cpf': error = cpfValid(value) ? '' : 'Digite o CPF do titular.'; break;
    }
    return fieldError(id, error);
  }
  function validateMany(ids) {
    let first = '';
    ids.forEach(id => { if (!validate(id) && !first) first = id; });
    if (first) {
      status('Confira os campos indicados para continuar.', 'error');
      el(first).focus();
    }
    return !first;
  }
  function selectedMethod() { return el('payment-card').checked ? 'card' : 'pix'; }
  function updateButton() {
    const button = el('purchase-button');
    const method = selectedMethod();
    el('reconcile-button').hidden = !state.uncertain;
    button.disabled = state.busy || state.pending || state.tokenizing || state.uncertain || !state.sessionId || !state.appmaxReady || (state.orderId && state.orderMethod !== method);
    button.textContent = state.busy || state.pending || state.tokenizing ? 'Aguarde...' : !state.appmaxReady ? 'Carregando pagamento...' : method === 'card' && !state.quote ? 'Continuar' : 'Comprar agora';
  }
  function switchMethod() {
    const card = selectedMethod() === 'card';
    el('card-fields').hidden = !card;
    el('pix-fields').hidden = card;
    el('card-option').classList.toggle('is-selected', card);
    el('pix-option').classList.toggle('is-selected', !card);
    el('payment-card').setAttribute('aria-expanded', String(card));
    el('payment-pix').setAttribute('aria-expanded', String(!card));
    if (state.orderId && state.orderMethod !== selectedMethod()) status('Este pedido já está aberto na forma de pagamento escolhida anteriormente. Consulte o resultado abaixo.', 'error');
    else status('');
    updateButton();
  }
  function showResult(title, message, type = 'info') {
    el('checkout-inputs').hidden = true;
    el('payment-result').hidden = false;
    el('result-title').textContent = title;
    el('result-message').textContent = message;
    el('payment-result').dataset.state = type;
    el('payment-result').scrollIntoView({ block: 'nearest' });
  }
  function setPix(pix) {
    if (!pix?.qr_code) return;
    el('pix-payment').hidden = false;
    el('pix-code').value = pix.qr_code;
    if (pix.qr_code_base64) {
      el('pix-qr').src = `data:image/png;base64,${pix.qr_code_base64}`;
      el('pix-qr').hidden = false;
    }
    if (pix.expires_at) {
      const expiry = new Date(pix.expires_at);
      el('pix-expiry').textContent = Number.isNaN(expiry.getTime()) ? '' : `Pague até ${expiry.toLocaleString('pt-BR')}.`;
    }
  }
  function saveSession() {
    try { sessionStorage.setItem(storageKey, JSON.stringify({ sessionId: state.sessionId, orderId: state.orderId, method: state.orderMethod })); } catch (_) { /* A página continua utilizável. */ }
  }
  function clearOrder() { try { sessionStorage.removeItem(storageKey); } catch (_) { /* Sem efeito. */ } }
  function applyOffer(offer) {
    if (offer?.product_name) {
      el('product-title').textContent = offer.product_name;
      el('order-product').textContent = offer.product_name;
    }
    const price = offer?.price_cents;
    if (!Number.isInteger(price) || price < 1) throw new Error('Oferta indisponível');
    el('product-price').textContent = `${money(price)} à vista`;
    el('order-total').textContent = money(price);
  }
  function updateOrderTotal() {
    const selected = state.quote?.options?.find(option => option.installments === Number(el('installments').value));
    const cents = selected?.total_cents || state.orderBaseTotal;
    if (Number.isInteger(cents) && cents > 0) el('order-total').textContent = money(cents);
  }
  async function reconcileSession() {
    if (!state.sessionId) return;
    const resumed = await get(`/sessoes/${encodeURIComponent(state.sessionId)}`);
    if (resumed.pedido_existente?.order_id) {
      normalizeOrder(resumed.pedido_existente, resumed.pedido_existente.method);
      state.uncertain = false;
      await poll();
    } else if (resumed.pedido_existente) {
      state.uncertain = false;
      showResult('Compra registrada', 'Este pedido já foi registrado. Consulte seu e-mail para acompanhar a compra.', 'info');
    } else {
      state.uncertain = false;
      status('O pedido não foi aberto. Confira os dados e tente novamente.', 'error');
    }
    updateButton();
  }
  async function poll() {
    if (!state.orderId) return;
    try {
      const order = await get(`/pedidos/${encodeURIComponent(state.orderId)}`);
      if (Number.isInteger(order.total_cents)) state.orderBaseTotal = order.total_cents;
      updateOrderTotal();
      clearTimeout(state.polling);
      if (order.status === 'pago') {
        el('pix-payment').hidden = true;
        showResult('Pagamento confirmado', 'Seu pagamento foi confirmado. Confira seu e-mail para acompanhar a compra.', 'success');
        return;
      }
      if (order.status === 'reembolsado') {
        el('pix-payment').hidden = true;
        showResult('Pagamento reembolsado', 'O reembolso deste pedido foi registrado.', 'info');
        return;
      }
      if (order.status === 'expirado') {
        el('pix-payment').hidden = true;
        showResult('Pedido expirado', 'Este pedido expirou. Volte à página do desafio para começar novamente.', 'error');
        return;
      }
      if (order.status === 'recusado' && state.orderMethod === 'card') {
        state.pending = false;
        el('checkout-inputs').hidden = false;
        el('payment-result').hidden = true;
        status('Cartão recusado. Confira os dados ou tente outro cartão.', 'error');
        updateButton();
        return;
      }
      if (state.orderMethod === 'pix') {
        showResult('Aguardando pagamento', 'Use o QR Code ou copie o código Pix. A confirmação aparecerá aqui.', 'info');
        setPix(order.pix);
      } else if (state.pending || order.card_in_review) {
        showResult('Pagamento em análise', 'Aguarde a confirmação. Não é preciso enviar outra compra.', 'info');
      }
      state.polling = setTimeout(poll, 4000);
    } catch (_) {
      clearTimeout(state.polling);
      if (state.pending || state.orderMethod === 'pix') showResult('Consultando pagamento', 'Não foi possível consultar agora. Tente novamente em instantes.', 'info');
      else status('Não foi possível consultar o pedido. Tente novamente.', 'error');
      state.polling = setTimeout(poll, 8000);
    }
  }
  async function loadQuote() {
    const quote = await get(`/pedidos/${encodeURIComponent(state.orderId)}/parcelas`);
    if (!Array.isArray(quote.options) || quote.options.length === 0) throw new Error('Sem parcelas');
    state.quote = quote;
    const select = el('installments');
    select.replaceChildren();
    quote.options.forEach(option => {
      const row = document.createElement('option');
      row.value = String(option.installments);
      row.textContent = option.installments === 1 ? `À vista — ${money(option.total_cents)}` : `${option.installments}x de ${money(option.installment_cents)} (total ${money(option.total_cents)})`;
      select.appendChild(row);
    });
    select.disabled = false;
    updateOrderTotal();
    updateButton();
  }
  function normalizeOrder(order, method) {
    state.orderId = order.order_id;
    state.orderMethod = order.payment?.method || order.method || method;
    formIds.forEach(id => { el(id).readOnly = true; });
    saveSession();
  }
  async function createOrder(method) {
    if (state.orderId) return;
    const customer = {
      name: el('buyer-name').value.trim(),
      email: el('buyer-email').value.trim(),
      cpf: digits(el('buyer-cpf').value),
      phone: digits(el('buyer-phone').value),
    };
    const payload = { customer, method, bump_ids: [], ...(state.ip ? { ip: state.ip } : {}) };
    try {
      normalizeOrder(await post(`/sessoes/${encodeURIComponent(state.sessionId)}/pedido`, payload), method);
    } catch (error) {
      if (error.status === 409 && error.body?.order_id) {
        normalizeOrder(error.body, method);
        if (state.orderMethod !== method) throw new Error('O pedido anterior usa outra forma de pagamento.');
        return;
      }
      // A resposta pode se perder depois de o pedido nascer. Não cria outro pedido.
      if (!error.status || (error.status >= 500 && error.status !== 502)) {
        state.uncertain = true;
        status('Não foi possível confirmar se o pedido foi aberto. Consulte o resultado antes de tentar novamente.', 'error');
        reconcileSession().catch(() => {});
      }
      throw error;
    }
  }
  async function purchase() {
    if (state.busy || state.pending || state.tokenizing || state.uncertain || !state.sessionId) return;
    const method = selectedMethod();
    if (state.orderId && state.orderMethod !== method) return;
    if ((!state.orderId && !validateMany(formIds)) || (method === 'card' && !validateMany(cardIds))) return;
    if (!state.appmaxReady) { status('Não foi possível carregar o pagamento. Recarregue a página e tente novamente.', 'error'); return; }
    state.busy = true;
    updateButton();
    try {
      if (!state.orderId) await createOrder(method);
      if (method === 'pix') {
        state.pending = true;
        await poll();
        return;
      }
      if (!state.quote) {
        await loadQuote();
        status('Confira o valor das parcelas e clique em Comprar agora.', 'info');
        el('installments').focus();
        return;
      }
      const installment = Number(el('installments').value);
      if (!state.quote.options.some(option => option.installments === installment)) {
        status('Escolha uma opção de parcelas.', 'error');
        return;
      }
      const [month, year] = el('card-expiry').value.split('/');
      el('card-number').value = digits(el('card-number').value);
      el('card-month').value = month;
      el('card-year').value = `20${year}`;
      state.tokenizing = true;
      state.submitAuthorized = true;
      el('card-form').requestSubmit(el('appmax-submit'));
      clearTimeout(state.tokenizeTimer);
      state.tokenizeTimer = setTimeout(() => {
        if (!state.tokenizing) return;
        state.tokenizing = false;
        state.submitAuthorized = false;
        status('A validação do cartão demorou. Confira os dados e tente novamente.', 'error');
        updateButton();
      }, 20000);
      status('Validando cartão...', 'info');
    } catch (error) {
      state.tokenizing = false;
      state.submitAuthorized = false;
      clearTimeout(state.tokenizeTimer);
      if (!state.uncertain) {
        status(error.message === 'O pedido anterior usa outra forma de pagamento.' ? error.message : 'Não foi possível continuar. Confira o pedido e tente novamente.', 'error');
      }
    } finally {
      state.busy = false;
      updateButton();
    }
  }
  async function confirmCard(token) {
    if (!state.tokenizing || state.pending || !state.orderId) return;
    state.tokenizing = false;
    clearTimeout(state.tokenizeTimer);
    state.pending = true;
    state.busy = true;
    updateButton();
    try {
      await post(`/pedidos/${encodeURIComponent(state.orderId)}/cartao`, {
        token,
        ip: state.ip,
        holder_name: el('card-holder').value.trim(),
        holder_document_number: digits(el('card-holder-cpf').value),
        installments: Number(el('installments').value),
      });
      await poll();
    } catch (error) {
      // A confirmação pode ter chegado ao provedor; consultar o pedido é seguro.
      if (error.status >= 400 && error.status < 500 && error.status !== 409) state.pending = false;
      await poll();
      if (!el('payment-result').hidden) return;
      status('Não foi possível concluir a tentativa. Consulte o pedido antes de tentar novamente.', 'error');
    } finally {
      state.busy = false;
      updateButton();
    }
  }
  function loadAppmax() {
    if (!config.externalId || !config.scriptURL) { status('O pagamento ainda não está disponível. Tente novamente mais tarde.', 'error'); return; }
    const script = document.createElement('script');
    script.src = config.scriptURL;
    script.async = true;
    script.onload = () => {
      if (!window.AppmaxScripts?.init) { status('Não foi possível carregar o pagamento. Recarregue a página.', 'error'); return; }
      try {
        window.AppmaxScripts.init({
          externalId: config.externalId,
          onIp: ({ ip }) => { state.ip = ip || ''; state.appmaxReady = Boolean(state.ip); updateButton(); },
          onTokenize: ({ token }) => confirmCard(token),
          onError: failure => {
            state.tokenizing = false;
            state.submitAuthorized = false;
            clearTimeout(state.tokenizeTimer);
            state.busy = false;
            updateButton();
            status(failure?.stage === 'tokenize' ? 'Não foi possível validar o cartão. Confira os dados e tente novamente.' : 'Não foi possível iniciar o pagamento. Recarregue a página e tente novamente.', 'error');
          },
        });
      } catch (_) { status('Não foi possível carregar o pagamento. Recarregue a página.', 'error'); }
    };
    script.onerror = () => status('Não foi possível carregar o pagamento. Recarregue a página e tente novamente.', 'error');
    document.head.appendChild(script);
  }
  async function init() {
    el('sandbox-banner').hidden = config.environment !== 'sandbox';
    el('copyright-year').textContent = String(new Date().getFullYear());
    ['payment-card', 'payment-pix'].forEach(id => el(id).addEventListener('change', switchMethod));
    el('purchase-button').addEventListener('click', purchase);
    el('card-form').addEventListener('submit', event => {
      if (state.submitAuthorized) {
        state.submitAuthorized = false;
        return;
      }
      event.preventDefault();
      event.stopImmediatePropagation();
    }, true);
    el('installments').addEventListener('change', updateOrderTotal);
    el('reconcile-button').addEventListener('click', () => reconcileSession().catch(() => status('Não foi possível consultar agora. Tente novamente em instantes.', 'error')));
    el('check-payment').addEventListener('click', () => state.orderId ? poll() : reconcileSession().catch(() => status('Não foi possível consultar agora. Tente novamente em instantes.', 'error')));
    el('copy-pix').addEventListener('click', async () => {
      try { await navigator.clipboard.writeText(el('pix-code').value); el('copy-pix').textContent = 'Código copiado'; }
      catch (_) { el('pix-code').select(); status('Selecione e copie o código Pix.', 'info'); }
    });
    [...formIds, ...cardIds].forEach(id => {
      el(id).addEventListener('blur', () => validate(id));
      el(id).addEventListener('input', () => { if (el(id).getAttribute('aria-invalid') === 'true') fieldError(id, ''); });
    });
    ['buyer-cpf', 'card-holder-cpf'].forEach(id => el(id).addEventListener('input', event => {
      const d = digits(event.target.value).slice(0, 11);
      event.target.value = d.replace(/^(\d{3})(\d)/, '$1.$2').replace(/^(\d{3})\.(\d{3})(\d)/, '$1.$2.$3').replace(/(\d{3})\.(\d{3})\.(\d{3})(\d)/, '$1.$2.$3-$4');
    }));
    el('buyer-phone').addEventListener('input', event => {
      const d = digits(event.target.value).slice(0, 11);
      event.target.value = d.length > 10 ? d.replace(/^(\d{2})(\d{5})(\d{0,4})$/, '($1) $2-$3') : d.replace(/^(\d{2})(\d{4})(\d{0,4})$/, '($1) $2-$3');
    });
    el('card-number').addEventListener('input', event => { event.target.value = digits(event.target.value).slice(0, 19).replace(/(.{4})/g, '$1 ').trim(); });
    el('card-expiry').addEventListener('input', event => { event.target.value = digits(event.target.value).slice(0, 4).replace(/^(\d{2})(\d)/, '$1/$2'); });
    el('card-cvv').addEventListener('input', event => { event.target.value = digits(event.target.value).slice(0, 4); });
    switchMethod();
    loadAppmax();
    try {
      let saved = null;
      try { saved = JSON.parse(sessionStorage.getItem(storageKey) || 'null'); } catch (_) { clearOrder(); }
      if (saved && /^[0-9a-f-]{36}$/i.test(saved.sessionId)) {
        state.sessionId = saved.sessionId;
        let resumed;
        try { resumed = await get(`/sessoes/${encodeURIComponent(state.sessionId)}`); }
        catch (error) {
          if (error.status !== 404) throw error;
          clearOrder();
          state.sessionId = '';
        }
        if (resumed) {
          applyOffer(resumed.offer);
          if (resumed.pedido_existente?.order_id) {
            normalizeOrder(resumed.pedido_existente, resumed.pedido_existente.method);
            el('personal-section').hidden = true;
            if (state.orderMethod === 'pix') el('payment-pix').checked = true;
            switchMethod();
            await poll();
            if (state.orderMethod === 'card' && el('payment-result').hidden) await loadQuote();
          } else if (resumed.pedido_existente) {
            showResult('Compra registrada', 'Este link de compra já foi usado. Consulte seu e-mail para acompanhar o pedido.', 'info');
          }
          updateButton();
          return;
        }
      }
      const query = new URLSearchParams(location.search);
      const utm = {};
      for (const key of ['utm_source', 'utm_medium', 'utm_campaign', 'utm_content', 'utm_term']) {
        const value = query.get(key);
        if (value) utm[key] = value.slice(0, 255);
      }
      const lead = query.get('lead');
      const payload = { offer_slug: config.offerSlug, utm, ...(lead ? { lead_id: lead } : {}) };
      const session = await post('/sessoes', payload);
      state.sessionId = session.id;
      saveSession();
      applyOffer(session.offer);
      if (session.pedido_existente?.order_id) {
        normalizeOrder(session.pedido_existente, session.pedido_existente.method);
        if (state.orderMethod === 'pix') el('payment-pix').checked = true;
        switchMethod();
        await poll();
        if (state.orderMethod === 'card' && el('payment-result').hidden) await loadQuote();
      } else if (session.pedido_existente) {
        showResult('Compra registrada', 'Este link de compra já foi usado. Consulte seu e-mail para acompanhar o pedido.', 'info');
      }
      updateButton();
    } catch (_) {
      status('Não foi possível carregar esta oferta. Recarregue a página e tente novamente.', 'error');
      el('product-price').textContent = 'Valor indisponível';
    }
  }
  init();
})();
