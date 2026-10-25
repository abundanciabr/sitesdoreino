'use strict';
(() => {
  if (window.MeshcraftFaixas) return;
  const assetRoot = new URL('.', document.currentScript.src).href;
  const nomes = ['Branca', 'Amarela', 'Azul', 'Vermelha', 'Verde', 'Marrom', 'Preta'];
  const cores = ['#f3f3ed', '#ffd447', '#64a6ff', '#ff6a77', '#70df95', '#d09a68', '#e4c986'];
  const filtros = ['grayscale(1) brightness(1.8)', 'none', 'hue-rotate(165deg) saturate(1.2)', 'hue-rotate(315deg) saturate(1.4)', 'hue-rotate(65deg)', 'saturate(.65) brightness(.56)', 'grayscale(1) brightness(.24)'];
  let atual = null;
  const adiadas = new Set();
  const node = (tag, cls, text) => {
    const n = document.createElement(tag); n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };
  function validar(progress, context) {
    if (!progress || !context || progress.pessoa_id !== context.pessoa_id || progress.site_id !== context.site_id
      || !Array.isArray(progress.etapas) || !Number.isInteger(progress.atual_ordem)) return [];
    const pendente = progress.celebracao;
    const fila = Array.isArray(pendente?.fila) ? pendente.fila : pendente?.ordem ? [pendente] : [];
    return fila.filter(p => p && Number.isInteger(p.ordem) && p.ordem >= 2 && p.ordem <= 13
      && p.ordem <= progress.atual_ordem && progress.etapas.some(e => e.ordem === p.ordem && e.alcancada === true)
      && Number.isSafeInteger(p.bonus_xp) && p.bonus_xp >= 0);
  }
  function belt(ordem, cls) {
    const i = Math.min(6, Math.max(0, ordem - 1));
    const image = node('img', 'mc-belt ' + cls);
    image.src = assetRoot + 'faixa_cerimonia-faixa.png'; image.alt = ''; image.width = 720; image.height = 720;
    image.style.filter = filtros[i]; image.setAttribute('aria-hidden', 'true');
    return image;
  }
  function celebrar(progress, context, options = {}) {
    const fila = validar(progress, context);
    if (!fila.length || atual) return false;
    const key = [context.site_id, context.pessoa_id, fila[0].ordem].join(':');
    if (adiadas.has(key) && !options.revelar) return false;
    const opener = document.activeElement;
    const dialog = node('dialog', 'mc-cerimonia');
    dialog.setAttribute('aria-labelledby', 'mc-cerimonia-title');
    const screen = node('section', 'mc-screen');
    const brand = node('p', 'mc-brand', options.demonstracao ? 'MESHCRAFT · DEMONSTRAÇÃO VISUAL' : '◇  MESHCRAFT');
    const close = node('button', 'mc-close', '×');
    close.type = 'button'; close.setAttribute('aria-label', 'Fechar por enquanto');
    const body = node('div', 'mc-body');
    const dots = node('div', 'mc-acts');
    dots.setAttribute('aria-label', 'Uma conquista em três atos');
    ['A tarefa', 'A revelação', 'A conquista'].forEach(text => dots.append(node('span', '', text)));
    screen.append(brand, close, body, dots); dialog.append(screen); document.body.append(dialog);
    let timer, index = 0, destroyed = false, audio;
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const state = {dialog, key}; atual = state;
    function destroy(done) {
      if (destroyed) return;
      destroyed = true; clearTimeout(timer); audio?.close().catch(() => {});
      dialog.close(); dialog.remove(); atual = null;
      document.documentElement.classList.remove('mc-celebrating');
      if (done && options.concluir) options.concluir();
      else if (opener?.isConnected) opener.focus({preventScroll:true});
      if (done) window.dispatchEvent(new Event('meshcraft:faixa-vista'));
    }
    function later() { adiadas.add(key); destroy(false); }
    close.addEventListener('click', later);
    dialog.addEventListener('cancel', event => { event.preventDefault(); later(); });
    const button = (text, action, cls = 'mc-action') => {
      const b = node('button', cls, text); b.type = 'button'; b.addEventListener('click', action); return b;
    };
    function sound() {
      if (reduced) return;
      try {
        const Audio = window.AudioContext || window.webkitAudioContext;
        if (!Audio) return;
        audio ||= new Audio(); audio.resume();
        [523.25, 659.25, 783.99, 1046.5].forEach((frequency, i) => {
          const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime + i * .12;
          o.type = 'sine'; o.frequency.value = frequency;
          g.gain.setValueAtTime(0, t); g.gain.linearRampToValueAtTime(.045, t + .025);
          g.gain.exponentialRampToValueAtTime(.001, t + .65);
          o.connect(g); g.connect(audio.destination); o.start(t); o.stop(t + .7);
        });
      } catch (_) { /* Som opcional; a conquista continua acessível. */ }
    }
    function stage(act) {
      clearTimeout(timer);
      const pending = fila[index], step = progress.etapas.find(e => e.ordem === pending.ordem);
      const previous = progress.etapas.find(e => e.ordem === pending.ordem - 1);
      const color = Math.min(6, pending.ordem - 1);
      screen.style.setProperty('--mc-accent', cores[color]);
      screen.dataset.act = String(act); body.replaceChildren();
      dots.childNodes.forEach((dot, i) => dot.setAttribute('aria-current', String(i === act - 1)));
      const eyebrow = node('p', 'mc-eyebrow', act === 1 ? 'REALIZAÇÃO RECONHECIDA' : act === 2 ? 'ESSE MOMENTO É SEU' : pending.ordem > 7 ? 'UM NOVO GRAU NA SUA HISTÓRIA' : 'VOCÊ MUDOU DE FAIXA!');
      const title = node('h1', 'mc-title'); title.id = 'mc-cerimonia-title'; title.tabIndex = -1;
      const art = node('div', 'mc-art'); art.setAttribute('aria-hidden', 'true');
      const light = node('div', 'mc-light'); art.append(light);
      if (act === 1) {
        title.textContent = options.tarefa?.titulo || 'Você fez acontecer.';
        art.append(node('div', 'mc-task-check', '✓'));
        const copy = node('p', 'mc-copy', options.tarefa?.feedback || step.conquista || 'Seu trabalho foi avaliado e reconhecido.');
        body.append(eyebrow, art, title, copy);
        const xp = options.tarefa?.xp;
        if (Number.isSafeInteger(xp) && xp > 0) {
          const reward = node('div', 'mc-reward mc-task-reward');
          reward.append(node('strong', '', '+' + xp.toLocaleString('pt-BR') + ' XP'), node('span', '', 'XP DA TAREFA'));
          body.append(reward);
        }
        body.append(button('VER MINHA CONQUISTA  →', () => stage(2)));
      } else if (act === 2) {
        title.textContent = pending.ordem > 7 ? 'Sua jornada continua crescendo.' : 'Uma nova cor na sua jornada.';
        art.append(belt(pending.ordem - 1, 'mc-belt-before'), node('div', 'mc-energy'), belt(pending.ordem, 'mc-belt-reveal'));
        body.append(eyebrow, title, art, node('p', 'mc-transition', (previous?.nome || nomes[Math.max(0, color - 1)]) + '  →  ' + step.nome));
        body.append(button('VER MINHA NOVA CONQUISTA  →', () => stage(3), 'mc-skip'));
        // Tempo da revelação, nunca um atraso para reconhecer a realização.
        timer = setTimeout(() => { if (!destroyed) stage(3); }, reduced ? 350 : 3200);
      } else {
        title.textContent = 'FAIXA ' + step.nome.toLocaleUpperCase('pt-BR') + '!';
        art.append(node('div', 'mc-energy'), belt(pending.ordem, 'mc-belt-earned'));
        if (pending.ordem >= 7 && progress.etapas.length === 13) {
          const roman = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII'][pending.ordem - 7];
          art.append(node('span', 'mc-degree', 'GRAU ' + roman));
        }
        const particles = node('div', 'mc-particles');
        for (let i = 0; i < 28; i++) {
          const p = node('i', ''); p.style.setProperty('--i', String(i)); particles.append(p);
        }
        art.append(particles);
        const message = pending.ordem === 2 ? 'Seu primeiro grande marco.' : pending.ordem === 7 && progress.etapas.length === 7 ? 'Seu primeiro ciclo de criação. Conquistado.' : pending.ordem > 7 ? 'Cada grau carrega a história do que você realizou.' : 'Seu trabalho ganhou uma nova cor.';
        body.append(eyebrow, title, node('p', 'mc-subtitle', message), art);
        const reward = node('div', 'mc-reward');
        reward.append(node('strong', '', pending.bonus_xp > 0 ? '+' + pending.bonus_xp.toLocaleString('pt-BR') + ' XP' : 'Conquista registrada'), node('span', '', pending.bonus_xp > 0 ? 'BÔNUS DA FAIXA' : 'SEU PROGRESSO ESTÁ PRESERVADO'));
        const error = node('p', 'mc-error'); error.setAttribute('role', 'status');
        const next = button(index < fila.length - 1 ? 'VER A PRÓXIMA CONQUISTA  →' : 'CONTINUAR MINHA JORNADA  →', async () => {
          if (options.demonstracao) {
            if (++index < fila.length) stage(1); else destroy(true);
            return;
          }
          next.disabled = true; error.textContent = 'Guardando este momento…';
          const data = new FormData();
          Object.entries({acao:'celebracao-vista', ordem:pending.ordem, contexto_pessoa:context.pessoa_id, contexto_site:context.site_id}).forEach(([k,v]) => data.append(k,v));
          try {
            const response = await fetch('/trilha/inventario/api/', {method:'POST', credentials:'same-origin', cache:'no-store', headers:{'X-CSRFToken':progress.csrf}, body:data});
            if (!response.ok) throw new Error();
            if (++index < fila.length) stage(1); else destroy(true);
          } catch (_) {
            next.disabled = false;
            error.textContent = 'Sua conquista está salva. Não foi possível confirmar a visualização; tente novamente ou feche por enquanto.';
          }
        });
        body.append(reward, next, error);
      }
      if (fila.length > 1) body.append(node('p', 'mc-queue', 'Sua conquista ' + (index + 1) + ' de ' + fila.length));
      if (act !== 2) title.focus({preventScroll:true});
    }
    document.documentElement.classList.add('mc-celebrating');
    dialog.showModal();
    stage(options.revelar ? 2 : 1);
    // O som só nasce de um gesto do aluno.
    dialog.addEventListener('click', event => {
      if (event.target.closest('.mc-action') && screen.dataset.act === '2') sound();
    });
    return true;
  }
  async function conferir() {
    if (document.hidden || atual || document.querySelector('.motivo-dialog[open]')) return;
    try {
      const response = await fetch('/trilha/minha-trilha/', {credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}});
      if (!response.ok) return;
      const progress = await response.json();
      const bootstrap = document.querySelector('#trilha-data');
      const context = bootstrap ? JSON.parse(bootstrap.textContent) : progress;
      celebrar(progress, context);
    } catch (_) { /* A próxima consulta retoma a mesma pendência do servidor. */ }
  }
  window.MeshcraftFaixas = {celebrar, validar, conferir, ativo:() => Boolean(atual)};
  if (document.querySelector('[data-faixa-acompanhar]')) {
    conferir();
    window.addEventListener('focus', conferir);
    document.addEventListener('visibilitychange', () => { if (!document.hidden) conferir(); });
    window.addEventListener('meshcraft:avaliacao-concluida', conferir);
    setInterval(conferir, 20000);
  }
})();

