(() => {
  "use strict";
  const panel = document.getElementById("wa-painel");
  if (!panel) return;
  const byId = id => document.getElementById(id);
  const form = byId("wa-form"), text = byId("wa-texto"), send = form.querySelector("button[type=submit]");
  const log = byId("wa-mensagens"), notice = byId("wa-recado"), model = byId("wa-modelo-nome");
  const drafts = new Map();
  let url = "", conversation = "", reference = "", cursor = "", generation = 0;
  let trigger = null, busy = false, loading = false, timer = null, signature = "";
  const saveDraft = () => { if (url) drafts.set(url, {text: text.value, model: model.value, reference}); };
  function message(item) {
    const bubble = document.createElement("div");
    bubble.className = "wa-mensagem" + (item.direcao === "saida" ? " saida" : "");
    bubble.dataset.id = item.id;
    bubble.append(document.createTextNode(item.texto));
    const detail = document.createElement("small");
    detail.textContent = [item.data, item.estado].filter(Boolean).join(" · ");
    bubble.append(detail);
    return bubble;
  }
  async function request(method, values = {}) {
    const target = url, current = generation;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    const options = {method, credentials: "same-origin", headers: {"Accept": "application/json"}, signal: controller.signal};
    let address = target;
    if (method === "POST") {
      options.body = new URLSearchParams({...values, csrfmiddlewaretoken: form.elements.csrfmiddlewaretoken.value});
    } else {
      address += "?" + new URLSearchParams({conversa_id: conversation, ...values});
    }
    try {
      const response = await fetch(address, options);
      if (!response.headers.get("content-type")?.includes("application/json")) throw new Error("A sessão ou a conexão mudou. Reabra a página para continuar.");
      const data = await response.json();
      if (current !== generation || panel.hidden) return null;
      if (!response.ok || data.erro) throw new Error(data.erro || "Não foi possível concluir. Atualize a conversa.");
      return data;
    } finally { clearTimeout(timeout); }
  }
  function draw(data, older = false) {
    conversation = data.conversa_id;
    reference ||= data.referencia;
    byId("wa-nome").textContent = data.nome;
    byId("wa-telefone").textContent = data.telefone;
    byId("wa-estado").textContent = data.estado;
    const external = byId("wa-aplicativo");
    external.href = data.aplicativo_url;
    external.hidden = false;
    byId("wa-devolver").hidden = !data.com_pessoa;
    byId("wa-modelo").hidden = data.texto_livre;
    text.disabled = false;
    send.disabled = busy;
    const updated = JSON.stringify(data.mensagens);
    if (older) {
      const height = log.scrollHeight;
      const ids = new Set(Array.from(log.querySelectorAll("[data-id]"), item => item.dataset.id));
      const fragment = document.createDocumentFragment();
      for (const item of data.mensagens) if (!ids.has(item.id)) fragment.append(message(item));
      log.querySelector(".wa-anteriores")?.remove();
      log.prepend(fragment);
      log.scrollTop += log.scrollHeight - height;
    } else if (updated !== signature) {
      const atBottom = log.scrollHeight - log.scrollTop - log.clientHeight < 90;
      log.replaceChildren();
      for (const item of data.mensagens) log.append(message(item));
      if (!data.mensagens.length) {
        const empty = document.createElement("p");
        empty.className = "wa-vazio";
        empty.textContent = "Nenhuma mensagem registrada ainda. Escreva para iniciar a conversa.";
        log.append(empty);
      }
      if (atBottom || !signature) log.scrollTop = log.scrollHeight;
      signature = updated;
    }
    cursor = data.antes_de || "";
    if (cursor && !log.querySelector(".wa-anteriores")) {
      const previous = document.createElement("button");
      previous.type = "button"; previous.className = "wa-anteriores";
      previous.textContent = "Ver mensagens anteriores";
      previous.addEventListener("click", () => refresh(true));
      log.prepend(previous);
    }
    if (data.descadastrado) notice.textContent = "Este contato pediu para não receber mensagens. O envio segue a preferência registrada.";
  }
  let viewingOlder = false;
  async function refresh(older = false) {
    if (!conversation || panel.hidden || loading || busy) return;
    if (viewingOlder && !older) return;
    loading = true;
    const current = generation;
    try {
      const data = await request("GET", older ? {antes_de: cursor} : {});
      if (data) { draw(data, older); if (older) viewingOlder = true; }
    } catch (error) { if (current === generation) notice.textContent = error.message; }
    finally { if (current === generation) loading = false; }
  }
  async function open(button) {
    if (busy) { notice.textContent = "Aguarde o resultado do envio antes de trocar de contato."; return; }
    saveDraft(); generation++; loading = false; viewingOlder = false;
    if (trigger) trigger.setAttribute("aria-expanded", "false");
    trigger = button; trigger.setAttribute("aria-expanded", "true");
    url = button.dataset.whatsappUrl; conversation = ""; signature = ""; cursor = "";
    const draft = drafts.get(url);
    text.value = draft?.text || ""; model.value = draft?.model || ""; reference = draft?.reference || "";
    panel.hidden = false; document.body.classList.add("wa-aberto");
    byId("wa-nome").textContent = button.dataset.whatsappNome;
    byId("wa-telefone").textContent = ""; byId("wa-estado").textContent = "";
    byId("wa-aplicativo").hidden = true; byId("wa-devolver").hidden = true; byId("wa-modelo").hidden = true;
    log.replaceChildren(); notice.textContent = "Abrindo conversa…";
    text.disabled = true; send.disabled = true;
    panel.querySelector(".wa-fechar").focus();
    const current = generation;
    try {
      const data = await request("POST", {acao: "abrir"});
      if (data) { notice.textContent = ""; draw(data); text.focus(); }
    } catch (error) { if (current === generation) notice.textContent = error.message; }
    clearInterval(timer);
    timer = setInterval(() => { if (!document.hidden) refresh(); }, 8000);
  }
  function close() {
    saveDraft(); generation++; panel.hidden = true;
    document.body.classList.remove("wa-aberto");
    clearInterval(timer); loading = false;
    if (trigger) { trigger.setAttribute("aria-expanded", "false"); trigger.focus(); }
  }
  document.addEventListener("click", event => {
    const button = event.target.closest("[data-whatsapp-url]");
    if (button) { event.preventDefault(); open(button); }
  });
  panel.querySelector(".wa-fechar").addEventListener("click", close);
  panel.addEventListener("keydown", event => { if (event.key === "Escape" && !busy) close(); });
  byId("wa-atualizar").addEventListener("click", () => {
    if (!conversation) { if (trigger) open(trigger); return; }
    viewingOlder = false; signature = ""; refresh();
  });
  async function action(kind) {
    if (busy || !conversation) return;
    if (kind === "enviar" && !text.value.trim() && (!model.value.trim() || byId("wa-modelo").hidden)) { text.focus(); return; }
    busy = true; send.disabled = true; text.disabled = true; model.disabled = true; byId("wa-devolver").disabled = true;
    panel.querySelector(".wa-fechar").disabled = true;
    notice.textContent = kind === "enviar" ? "Enviando…" : "Devolvendo ao assistente…";
    try {
      const data = await request("POST", {acao: kind, texto: text.value,
        modelo: byId("wa-modelo").hidden ? "" : model.value, referencia: reference});
      if (data) {
        notice.textContent = data.recado;
        if (data.resultado === "ok") {
          if (kind === "enviar") { text.value = ""; model.value = ""; }
          reference = data.referencia; saveDraft();
        }
      }
    } catch (error) {
      notice.textContent = "Não foi possível confirmar a operação. Confira o histórico antes de repetir. " + error.message;
      saveDraft();
    } finally {
      busy = false; send.disabled = false; text.disabled = false; model.disabled = false; byId("wa-devolver").disabled = false;
      panel.querySelector(".wa-fechar").disabled = false;
      viewingOlder = false; signature = ""; await refresh();
    }
  }
  form.addEventListener("submit", event => { event.preventDefault(); action("enviar"); });
  byId("wa-devolver").addEventListener("click", () => action("devolver"));
  text.addEventListener("input", saveDraft); model.addEventListener("input", saveDraft);
})();
