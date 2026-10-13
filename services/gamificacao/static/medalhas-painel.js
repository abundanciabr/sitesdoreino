(() => {
  "use strict";
  if (window.meshcraftMedalhas) return;
  window.meshcraftMedalhas = true;
  const base = "/conquistas/minhas-medalhas/";
  const previaNode = document.getElementById("medalha-previa");
  let dados = {medalhas: []}, aberta = false, consultando = false, botaoColecao;
  const estilo = document.createElement("link");
  estilo.rel = "stylesheet"; estilo.href = "/conquistas/static/medalhas-painel.css?v=20261012-1";
  document.head.append(estilo);
  const el = (tag, classe, texto) => {
    const node = document.createElement(tag);
    if (classe) node.className = classe;
    if (texto !== undefined) node.textContent = texto;
    return node;
  };
  const selo = () => {
    const node = el("div", "mc-med-selo");
    node.setAttribute("aria-hidden", "true");
    node.innerHTML = '<svg viewBox="0 0 240 260"><defs><linearGradient id="mc-med-ouro" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff0ad"/><stop offset=".48" stop-color="#e9b749"/><stop offset="1" stop-color="#b57920"/></linearGradient><linearGradient id="mc-med-miolo" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff9da"/><stop offset="1" stop-color="#f6d87f"/></linearGradient></defs><path d="m74 171-12 74 42-20 20 29 13-81m30-2 11 74-41-20-20 29-11-81" fill="#176955"/><path d="m79 187-6 40 28-13 15 20 7-40m35-7 7 40-28-13-15 20-7-40" fill="#269075"/><circle cx="120" cy="112" r="91" fill="url(#mc-med-ouro)" stroke="#ba862c" stroke-width="2"/><circle cx="120" cy="112" r="78" fill="none" stroke="#ffefb5" stroke-width="3"/><circle cx="120" cy="112" r="65" fill="url(#mc-med-miolo)" stroke="#cf9f38"/><path d="m120 68 13 27 30 4-22 21 5 31-26-15-26 15 5-31-22-21 30-4Z" fill="#b57c21"/><path d="m120 72 12 26 27 4-20 19 5 26-24-13-24 13 5-26-20-19 27-4Z" fill="#fff3be"/><g fill="#fff5cc"><circle cx="120" cy="30" r="3"/><circle cx="38" cy="112" r="3"/><circle cx="202" cy="112" r="3"/><circle cx="62" cy="54" r="3"/><circle cx="178" cy="54" r="3"/><circle cx="63" cy="170" r="3"/><circle cx="177" cy="170" r="3"/></g></svg>';
    return node;
  };
  function moldura(rotulo) {
    const dialog = el("dialog", "mc-med-dialog");
    dialog.setAttribute("aria-label", rotulo);
    const tela = el("section", "mc-med-tela");
    const topo = el("header", "mc-med-topo");
    topo.append(el("span", "mc-med-marca", "MESHCRAFT"), el("span", "mc-med-legenda", previaNode ? "PRÉVIA · NENHUMA MEDALHA CONCEDIDA" : "SUA HISTÓRIA MERECE SER CELEBRADA"));
    tela.append(topo); dialog.append(tela);
    document.body.append(dialog);
    aberta = true;
    dialog.showModal();
    return {dialog, tela};
  }
  function fechar(dialog) {
    dialog.close(); dialog.remove(); aberta = false;
  }
  function celebrar(medalha, pendente = false) {
    if (aberta) return;
    const {dialog, tela} = moldura("Você recebeu a medalha " + medalha.nome);
    const confete = el("div", "mc-med-confete");
    confete.setAttribute("aria-hidden", "true");
    for (let i = 0; i < 26; i++) {
      const tira = el("i"); tira.style.setProperty("--i", i); confete.append(tira);
    }
    const corpo = el("main", "mc-med-corpo");
    corpo.append(confete, selo(), el("p", "mc-med-sobrancelha", "UM RECONHECIMENTO ESPECIAL"),
      el("h1", "mc-med-titulo", medalha.nome), el("p", "mc-med-subtitulo", "Esta conquista é sua."),
      el("p", "mc-med-mensagem", medalha.mensagem));
    const assinatura = el("p", "mc-med-assinatura", "Com carinho, equipe Meshcraft");
    const botao = el("button", "mc-med-botao", previaNode ? "Rever animação" : "Que alegria! Continuar");
    botao.type = "button";
    const aviso = el("p", "mc-med-aviso", previaNode ? "Assim o aluno verá a medalha. Esta prévia não concede nada." : "Guardada para sempre na sua coleção de medalhas.");
    const erro = el("p", "mc-med-erro"); erro.setAttribute("role", "alert");
    corpo.append(assinatura, botao, aviso, erro); tela.append(corpo);
    const concluir = async () => {
      if (previaNode) { fechar(dialog); celebrar(medalha); return; }
      botao.disabled = true;
      if (pendente) {
        try {
          const resposta = await fetch(base + medalha.id + "/vista/", {
            method: "POST", credentials: "same-origin", headers: {"X-CSRFToken": dados.csrf}
          });
          const corpo = await resposta.json();
          if (!resposta.ok || corpo.vista !== true) throw new Error("não confirmado");
        } catch (_) {
          erro.textContent = "Sua medalha está guardada. Não conseguimos registrar que você viu a celebração. Tente novamente.";
          botao.disabled = false; botao.textContent = "Tentar novamente"; return;
        }
      }
      fechar(dialog);
      consultar(false);
    };
    botao.addEventListener("click", concluir);
    dialog.addEventListener("cancel", e => { e.preventDefault(); concluir(); });
    botao.focus({preventScroll: true});
  }
  function colecao() {
    if (aberta) return;
    const {dialog, tela} = moldura("Minha coleção de medalhas");
    const corpo = el("main", "mc-med-colecao");
    corpo.append(el("p", "mc-med-sobrancelha", "CADA RECONHECIMENTO, UMA HISTÓRIA"), el("h1", "mc-med-titulo", "Minhas medalhas"));
    const lista = el("div", "mc-med-lista");
    for (const m of dados.medalhas) {
      const item = el("button", "mc-med-item"); item.type = "button";
      item.append(el("span", "mc-med-mini", "✦"), el("strong", "", m.nome), el("span", "", m.mensagem), el("small", "", "Rever conquista →"));
      item.addEventListener("click", () => { fechar(dialog); celebrar(m, !m.vista); });
      lista.append(item);
    }
    const voltar = el("button", "mc-med-botao", "Voltar"); voltar.type = "button";
    voltar.addEventListener("click", () => fechar(dialog));
    dialog.addEventListener("cancel", e => { e.preventDefault(); fechar(dialog); });
    corpo.append(lista, voltar); tela.append(corpo); voltar.focus({preventScroll: true});
  }
  function livre() {
    const foco = document.activeElement;
    return !document.hidden && !aberta && !document.querySelector("dialog[open]") &&
      !foco?.matches("input,textarea,select,[contenteditable=true]") &&
      !Array.from(document.querySelectorAll("video,audio")).some(v => !v.paused);
  }
  async function consultar(exibir = true) {
    if (consultando || document.hidden || aberta) return;
    consultando = true;
    try {
      const resposta = await fetch(base, {credentials: "same-origin", cache: "no-store"});
      if (!resposta.ok) return;
      const novo = await resposta.json();
      if (!Array.isArray(novo.medalhas)) return;
      dados = novo;
      if (dados.medalhas.length && !botaoColecao) {
        botaoColecao = el("button", "mc-med-abrir", "✦ Minhas medalhas");
        botaoColecao.type = "button"; botaoColecao.addEventListener("click", colecao);
        document.body.append(botaoColecao);
      } else if (!dados.medalhas.length && botaoColecao) {
        botaoColecao.remove(); botaoColecao = null;
      }
      if (exibir && dados.pendente && livre()) celebrar(dados.pendente, true);
    } catch (_) { /* A aula continua disponível se a consulta falhar. */ }
    finally { consultando = false; }
  }
  function iniciar() {
    if (previaNode) { celebrar(JSON.parse(previaNode.textContent)); return; }
    if (window.top !== window.self) return;
    consultar();
    window.setInterval(() => { if (livre()) consultar(); }, 30000);
    document.addEventListener("visibilitychange", () => { if (livre()) consultar(); });
  }
  if (estilo.sheet) iniciar();
  else { estilo.addEventListener("load", iniciar, {once: true}); estilo.addEventListener("error", iniciar, {once: true}); }
})();
