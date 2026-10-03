(() => {
  "use strict";
  const form = document.getElementById("apresentacao");
  if (!form) return;
  const $ = (selector, root = document) => root.querySelector(selector);
  const initialNode = $("#conteudo-inicial");
  let saved = {};
  try { saved = JSON.parse(initialNode?.textContent || "{}") || {}; } catch (_) { saved = {}; }
  const pageFields = [
    ["titulo", "Título", "Abertura", "text", 200],
    ["subtitulo", "Subtítulo", "Abertura", "textarea"],
    ["apresentacao", "Quem sou e o que faço", "Apresentação", "textarea", 3000],
    ["oferta", "O que posso entregar", "Oferta", "textarea", 3000],
    ["diferenciais", "Diferenciais, um por linha", "Diferenciais", "textarea"],
    ["condicoes", "Condições, uma por linha", "Condições", "textarea"],
    ["continuidade", "Como seguimos depois", "Continuidade", "textarea"],
    ["duvidas", "Dúvidas frequentes, uma por linha", "Dúvidas", "textarea"],
    ["cta", "Convite para contato", "Convite para contato", "text"]
  ];
  const kitFields = [
    ["apresentacao_principal", "Bio longa", "Apresentação principal", "textarea"],
    ["bio_curta", "Bio curta", "Bio curta", "textarea", 280],
    ["abordagem", "Mensagem para o destinatário", "Primeira abordagem", "textarea"],
    ["proposta", "Texto da proposta", "Proposta", "textarea"]
  ];
  const positionFields = [["comprador", "Comprador"], ["necessidade", "Necessidade"], ["oferta", "Oferta prioritária"], ["prova", "O que demonstra meu trabalho"]];
  const allFields = [...pageFields.map(([key]) => `pagina.${key}`), ...kitFields.map(([key]) => `kit.${key}`)];
  const initial = {
    versao: 1,
    posicionamento: {comprador: "", necessidade: "", oferta: "", prova: ""},
    pagina: {titulo: "", subtitulo: "", apresentacao: "", oferta: "", continuidade: "", diferenciais: "", condicoes: "", duvidas: "", cta: "", trabalho_destaque: "", legendas: []},
    kit: {apresentacao_principal: "", bio_curta: "", abordagem: "", proposta: ""}
  };
  const content = {
    ...initial, ...saved,
    posicionamento: {...initial.posicionamento, ...(saved.posicionamento || {})},
    pagina: {...initial.pagina, ...(saved.pagina || {})},
    kit: {...initial.kit, ...(saved.kit || {})}
  };
  if (!content.pagina.apresentacao) content.pagina.apresentacao = form.dataset.apresentacaoLegada || "";
  if (!content.pagina.oferta) content.pagina.oferta = form.dataset.servicoLegado || "";
  if (!content.posicionamento.comprador) content.posicionamento.comprador = form.elements.namedItem("oferta_comprador")?.value || "";
  if (!content.posicionamento.oferta) content.posicionamento.oferta = form.elements.namedItem("oferta_encomenda")?.value || "";
  const savedLegends = Array.isArray(content.pagina.legendas) ? content.pagina.legendas : [];
  const fieldElements = new Map();
  const positionPanel = document.createElement("section"); positionPanel.className = "ap-panel";
  const positionHeading = document.createElement("h2"); positionHeading.textContent = "Síntese do meu posicionamento";
  const positionHelp = document.createElement("p"); positionHelp.textContent = "Resuma para quem você trabalha, qual necessidade atende e o que pode mostrar como prova.";
  const positionGrid = document.createElement("div"); positionGrid.className = "ap-fields";
  positionPanel.append(positionHeading, positionHelp, positionGrid);
  $(".ap-tabs").before(positionPanel);
  for (const [key, label] of positionFields) {
    const wrap = document.createElement("div"); wrap.className = "ap-field";
    const caption = document.createElement("label"); caption.htmlFor = `posicionamento_${key}`; caption.textContent = label;
    const input = document.createElement("input"); input.id = caption.htmlFor; input.name = input.id; input.value = String(content.posicionamento[key] || "");
    wrap.append(caption, input); positionGrid.append(wrap); fieldElements.set(`posicionamento.${key}`, input);
  }
  function makeField(group, spec, mount) {
    const [key, label, title, kind, max] = spec;
    const path = `${group}.${key}`;
    const panel = document.createElement("section"); panel.className = "ap-panel";
    const row = document.createElement("div"); row.className = "ap-row";
    const heading = document.createElement("h2"); heading.textContent = title;
    const button = document.createElement("button"); button.type = "button"; button.className = "ap-generate"; button.dataset.gerar = path; button.textContent = "Gerar esta seção";
    row.append(heading, button);
    if (group === "kit") {
      const copy = document.createElement("button"); copy.type = "button"; copy.className = "ap-generate"; copy.dataset.copy = path; copy.textContent = "Copiar"; row.append(copy);
    }
    panel.append(row);
    const status = document.createElement("p"); status.className = "ap-status"; status.dataset.status = path; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); panel.append(status);
    const wrapper = document.createElement("div"); wrapper.className = "ap-field";
    const caption = document.createElement("label"); caption.htmlFor = `${group}_${key}`; caption.textContent = label;
    const input = document.createElement(kind === "textarea" ? "textarea" : "input");
    input.id = `${group}_${key}`; input.name = input.id;
    if (kind !== "textarea") input.type = "text";
    if (max) input.maxLength = max;
    input.value = String(content[group][key] || "");
    wrapper.append(caption, input);
    if (path === "kit.bio_curta") {
      const counter = document.createElement("small"); counter.id = "bio-contador"; counter.className = "ap-counter"; counter.setAttribute("aria-live", "polite"); wrapper.append(counter);
    }
    panel.append(wrapper); mount.append(panel); fieldElements.set(path, input);
  }
  pageFields.forEach(spec => makeField("pagina", spec, $("#campos-pagina")));
  kitFields.forEach(spec => makeField("kit", spec, $("#campos-kit")));
  const works = [...form.querySelectorAll(".ap-work")];
  for (const work of works) {
    const id = work.dataset.workId;
    const savedLegend = savedLegends.find(item => String(item.peca_id) === id);
    const title = $(`[name="legenda_titulo_${id}"]`, work);
    const description = $(`[name="legenda_texto_${id}"]`, work);
    title.value = savedLegend?.titulo || work.dataset.workTitle || "";
    description.value = savedLegend?.texto || work.dataset.workText || "";
  }
  const proofTypes = [["render", "Render final"], ["detalhe", "Detalhe"], ["wireframe", "Wireframe"], ["studio", "Teste Studio"], ["video", "Vídeo"]];
  for (const work of works) {
    const id = work.dataset.workId;
    const raw = $(`[name="provas_${id}"]`, work);
    const editor = $(`[data-proofs-for="${id}"]`, work);
    if (!raw || !editor) continue;
    raw.hidden = true; raw.style.display = "none";
    const list = document.createElement("div"); editor.append(list);
    const add = document.createElement("button"); add.type = "button"; add.className = "ap-generate"; add.textContent = "Adicionar prova"; editor.append(add);
    const serialize = () => {
      raw.value = [...list.children].map(row => {
        const type = $("select", row).value;
        const url = $("[data-proof-link]", row).value.trim();
        const description = $("[data-proof-description]", row).value.trim();
        return url ? `${type} | ${url} | ${description}` : "";
      }).filter(Boolean).join("\n");
    };
    function addRow(type = "render", url = "", description = "") {
      if (list.children.length >= 8) return;
      const row = document.createElement("div"); row.className = "ap-fields";
      const typeWrap = document.createElement("div"); typeWrap.className = "ap-field";
      const typeLabel = document.createElement("label"); typeLabel.textContent = "Tipo de prova";
      const select = document.createElement("select");
      proofTypes.forEach(([value, label]) => { const option = document.createElement("option"); option.value = value; option.textContent = label; select.append(option); });
      select.value = type; typeLabel.append(select); typeWrap.append(typeLabel);
      const urlWrap = document.createElement("div"); urlWrap.className = "ap-field";
      const urlLabel = document.createElement("label"); urlLabel.textContent = "Link público";
      const link = document.createElement("input"); link.type = "text"; link.inputMode = "url"; link.dataset.proofLink = ""; link.placeholder = "https://..."; link.value = url; urlLabel.append(link); urlWrap.append(urlLabel);
      const descWrap = document.createElement("div"); descWrap.className = "ap-field wide";
      const descLabel = document.createElement("label"); descLabel.textContent = "Descrição";
      const desc = document.createElement("input"); desc.type = "text"; desc.dataset.proofDescription = ""; desc.value = description; descLabel.append(desc); descWrap.append(descLabel);
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "ap-generate"; remove.textContent = "Remover prova";
      remove.addEventListener("click", () => { row.remove(); add.disabled = false; serialize(); sync(); });
      row.append(typeWrap, urlWrap, descWrap, remove); list.append(row);
      row.addEventListener("input", serialize); row.addEventListener("change", serialize);
      serialize();
    }
    const existing = raw.value.split(/\r?\n/).map(line => line.split("|", 3).map(part => part.trim())).filter(parts => parts.length >= 2 && parts[1]);
    existing.forEach(parts => addRow(parts[0], parts[1], parts[2] || ""));
    add.addEventListener("click", () => { addRow(); add.disabled = list.children.length >= 8; });
    if (existing.length >= 8) add.disabled = true;
  }
  const heroInput = $("#pagina_trabalho_destaque");
  heroInput.value = String(content.pagina.trabalho_destaque || "");
  heroInput.addEventListener("change", () => {
    const work = works.find(item => item.dataset.workId === heroInput.value);
    if (work) $("[name=trabalhos_ids]", work).checked = true;
    sync();
  });
  const workPanel = works[0]?.closest(".ap-panel");
  if (workPanel) {
    const heading = $("h2", workPanel);
    const row = document.createElement("div"); row.className = "ap-row";
    heading.replaceWith(row); row.append(heading);
    const button = document.createElement("button"); button.type = "button"; button.className = "ap-generate"; button.dataset.gerar = "pagina.legendas"; button.textContent = "Gerar legendas"; row.append(button);
    const status = document.createElement("p"); status.className = "ap-status"; status.dataset.status = "pagina.legendas"; status.setAttribute("role", "status"); status.setAttribute("aria-live", "polite"); row.after(status);
  }
  const hidden = $("#conteudo-json");
  const get = path => {
    const [group, key] = path.split(".");
    return String(content[group]?.[key] || "");
  };
  const setText = (id, value, fallback = "Escreva aqui para ver a prévia.") => {
    const element = document.getElementById(id);
    if (!element) return;
    element.textContent = value || fallback;
    element.classList.toggle("ap-empty", !value);
  };
  function sync() {
    allFields.forEach(path => {
      const [group, key] = path.split(".");
      content[group][key] = fieldElements.get(path).value;
    });
    positionFields.forEach(([key]) => { content.posicionamento[key] = fieldElements.get(`posicionamento.${key}`).value; });
    content.pagina.trabalho_destaque = heroInput.value;
    content.pagina.legendas = works.map(work => ({
      peca_id: work.dataset.workId,
      titulo: $(`[name="legenda_titulo_${work.dataset.workId}"]`, work).value,
      texto: $(`[name="legenda_texto_${work.dataset.workId}"]`, work).value
    })).filter(item => item.titulo || item.texto);
    hidden.value = JSON.stringify(content);
    const bio = $("#bio-contador"); if (bio) bio.textContent = `${get("kit.bio_curta").length}/280`;
    render();
  }
  function render() {
    for (const key of ["titulo", "subtitulo", "apresentacao", "oferta", "diferenciais", "condicoes", "continuidade", "duvidas"])
      setText(`preview-${key}`, get(`pagina.${key}`));
    const contact = $("#preview-cta");
    contact.textContent = get("pagina.cta") || "Entrar em contato";
    const contactValue = form.elements.namedItem("oferta_contato")?.value || "";
    let safeContact = "";
    try { const url = new URL(contactValue); if (["https:", "http:"].includes(url.protocol)) safeContact = url.href; } catch (_) { /* sem link */ }
    contact.href = safeContact || "#";
    contact.setAttribute("aria-disabled", safeContact ? "false" : "true");
    let details = $("#preview-detalhes");
    if (!details) {
      details = document.createElement("div"); details.id = "preview-detalhes";
      $("#preview-trabalhos").before(details);
    }
    details.replaceChildren();
    const facts = [
      ["Entrega", "entregaveis"], ["Formatos", "formatos"], ["Prazo", "prazo"],
      ["Revisões", "revisoes"], ["Suporte", "suporte"]
    ];
    if (form.elements.namedItem("oferta_exibir_preco")?.checked) facts.push(["Preço", "preco"]);
    for (const [label, name] of facts) {
      const value = form.elements.namedItem(`oferta_${name}`)?.value?.trim();
      if (!value) continue;
      const paragraph = document.createElement("p");
      const strong = document.createElement("strong"); strong.textContent = `${label}: `;
      paragraph.append(strong, document.createTextNode(value)); details.append(paragraph);
    }
    const selected = works.filter(work => $("[name=trabalhos_ids]", work).checked);
    const heroWork = selected.find(work => work.dataset.workId === heroInput.value) || selected[0];
    const hero = $("#preview-hero"); hero.hidden = !heroWork;
    if (heroWork) { hero.src = heroWork.dataset.workImage; hero.alt = $("label", heroWork).textContent.trim(); }
    else hero.removeAttribute("src");
    const grid = $("#preview-trabalhos"); grid.replaceChildren();
    for (const work of selected) {
      const id = work.dataset.workId;
      const card = document.createElement("div"); card.className = "ap-preview-card";
      const img = document.createElement("img"); img.src = work.dataset.workImage; img.alt = ""; img.loading = "lazy";
      const title = document.createElement("strong"); title.textContent = $(`[name="legenda_titulo_${id}"]`, work).value || $("label", work).textContent.trim();
      const description = document.createElement("span"); description.textContent = $(`[name="legenda_texto_${id}"]`, work).value || $("small", work).textContent.trim();
      card.append(img, title, description); grid.append(card);
    }
    const kitPreviews = {apresentacao_principal: "apresentacao-principal", bio_curta: "bio-curta", abordagem: "abordagem", proposta: "proposta"};
    Object.entries(kitPreviews).forEach(([key, id]) => setText(`preview-${id}`, get(`kit.${key}`)));
  }
  form.addEventListener("input", sync);
  form.addEventListener("change", sync);
  form.addEventListener("submit", event => {
    if (pending > 0) {
      event.preventDefault();
      $("#status-salvar").textContent = "Aguarde a sugestão terminar para salvar.";
      return;
    }
    sync(); $("#status-salvar").textContent = "Salvando...";
  });
  const tabs = [...form.querySelectorAll(".ap-tab")];
  function openTab(which) {
    tabs.forEach(tab => { const active = tab.id === `tab-${which}`; tab.setAttribute("aria-selected", String(active)); tab.tabIndex = active ? 0 : -1; });
    $("#painel-pagina").hidden = which !== "pagina";
    $("#painel-kit").hidden = which !== "kit";
    $("#preview-pagina").hidden = which !== "pagina";
    $("#preview-kit").hidden = which !== "kit";
  }
  tabs.forEach(tab => tab.addEventListener("click", () => openTab(tab.id.slice(4))));
  async function copyText(value) {
    if (navigator.clipboard?.writeText) {
      try { await navigator.clipboard.writeText(value); return true; } catch (_) { /* usar alternativa */ }
    }
    const scratch = document.createElement("textarea");
    scratch.value = value; scratch.style.position = "fixed"; scratch.style.left = "-9999px";
    document.body.append(scratch); scratch.select();
    let copied = false;
    try { copied = document.execCommand("copy"); } catch (_) { /* navegador sem cópia */ }
    scratch.remove(); return copied;
  }
  form.querySelectorAll("[data-copy]").forEach(button => button.addEventListener("click", async () => {
    const path = button.dataset.copy;
    const status = form.querySelector(`[data-status="${path}"]`);
    const value = fieldElements.get(path)?.value || "";
    if (!value.trim()) { status.textContent = "Escreva ou gere o texto antes de copiar."; return; }
    status.textContent = await copyText(value) ? "Texto copiado." : "Não foi possível copiar. Selecione o texto acima para copiar.";
  }));
  function fieldsFor(requested) {
    return requested === "completo" ? [...allFields, ...positionFields.map(([key]) => `posicionamento.${key}`), "pagina.trabalho_destaque", "pagina.legendas"] : requested.split(",");
  }
  function snapshot(paths) {
    const values = {};
    paths.forEach(path => { values[path] = path === "pagina.legendas" ? JSON.stringify(content.pagina.legendas) : get(path); });
    return values;
  }
  function applyResult(result, paths, before) {
    const data = result?.conteudo;
    if (!data || typeof data !== "object") throw new Error(result?.erro || "A geração não trouxe textos. Seu rascunho foi mantido.");
    let applied = 0;
    for (const path of paths) {
      const [group, key] = path.split(".");
      const value = data[group]?.[key];
      if (value === undefined || value === null) continue;
      const current = path === "pagina.legendas" ? JSON.stringify(content.pagina.legendas) : get(path);
      if (current !== before[path]) continue;
      if (path === "pagina.legendas" && Array.isArray(value)) {
        for (const work of works) {
          const item = value.find(legend => String(legend.peca_id) === work.dataset.workId);
          if (!item) continue;
          const id = work.dataset.workId;
          $(`[name="legenda_titulo_${id}"]`, work).value = String(item.titulo || "");
          $(`[name="legenda_texto_${id}"]`, work).value = String(item.texto || "");
        }
        applied++;
      } else if (path === "pagina.trabalho_destaque" && typeof value === "string") {
        heroInput.value = value; applied++;
      } else if (typeof value === "string" && fieldElements.has(path)) {
        fieldElements.get(path).value = value; applied++;
      }
    }
    sync();
    if (!applied) throw new Error("Os textos foram alterados enquanto o robô gerava. Suas edições foram mantidas.");
    return applied;
  }
  let pending = 0;
  const saveButton = $("#salvar-apresentacao");
  async function generateOne(path, status, scope = null) {
    sync();
    const paths = scope || fieldsFor(path);
    const before = snapshot(paths);
    const body = new FormData(form);
    body.set("campo", path);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 145000);
    let response;
    try {
      response = await fetch(form.dataset.gerador, {method: "POST", credentials: "same-origin", headers: {"X-CSRFToken": body.get("csrfmiddlewaretoken")}, body, signal: controller.signal});
    } catch (_) {
      throw new Error("A sugestão demorou demais ou a conexão falhou. Seu rascunho foi mantido.");
    } finally { clearTimeout(timeout); }
    let result;
    try { result = await response.json(); } catch (_) { throw new Error("Não foi possível gerar agora. Seu rascunho foi mantido."); }
    if (!response.ok) throw new Error(result?.erro || "Não foi possível gerar agora. Seu rascunho foi mantido.");
    applyResult(result, paths, before);
    status.textContent = result.visao ? "Sugestão pronta com as imagens dos trabalhos. Você pode editar e salvar." : "Sugestão pronta a partir dos seus textos e dados. Você pode editar e salvar.";
  }
  form.querySelectorAll("[data-gerar]").forEach(button => button.addEventListener("click", async () => {
    const requested = button.dataset.gerar;
    const status = form.querySelector(`[data-status="${requested}"]`);
    const original = button.textContent;
    button.disabled = true; button.textContent = "Gerando...";
    pending++; saveButton.disabled = true;
    status.textContent = "Preparando sugestão...";
    try {
      if (requested.startsWith("kit.") && requested.includes(",")) {
        await generateOne("completo", status, kitFields.map(([key]) => `kit.${key}`));
      } else {
        await generateOne(requested, status);
      }
    } catch (error) { status.textContent = error.message || "Não foi possível gerar agora. Seu rascunho foi mantido."; }
    finally { pending--; saveButton.disabled = pending > 0; button.disabled = false; button.textContent = original; }
  }));
  openTab("pagina"); sync();
})();
