(() => {
  'use strict';
  const form = document.getElementById('portfolio-montagem');
  if (!form) return;
  const status = document.getElementById('portfolio-status');
  const detail = document.getElementById('portfolio-status-detail');
  const preview = document.getElementById('portfolio-preview');
  let initial = JSON.parse(document.getElementById('conteudo-inicial').textContent || '{}');
  let highlight = initial.pagina?.trabalho_destaque || '';
  let timer, dirty = false, revision = 0, queue = Promise.resolve();
  const rows = () => [...form.querySelectorAll('.pf-work')];
  function sync() {
    const data = structuredClone(initial);
    data.pagina ||= {};
    for (const input of form.querySelectorAll('[name^="pagina_"]')) data.pagina[input.name.slice(7)] = input.value;
    data.pagina.apelido_rascunho = form.elements.apelido.value;
    data.pagina.trabalho_destaque = highlight;
    data.pagina.ordem_trabalhos = rows().map(row => row.dataset.id);
    data.pagina.materiais_ids = [...form.querySelectorAll('[name="materiais_ids"]:checked')].map(input => input.value);
    data.pagina.legendas = rows().map(row => ({peca_id:row.dataset.id, titulo:form.elements['legenda_titulo_' + row.dataset.id].value, texto:form.elements['legenda_texto_' + row.dataset.id].value}));
    document.getElementById('conteudo-json').value = JSON.stringify(data);
    form.querySelectorAll('[data-destaque]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.destaque === highlight)));
    const order = data.pagina.ordem_trabalhos;
    rows().sort((a,b) => order.indexOf(a.dataset.id) - order.indexOf(b.dataset.id));
    form.querySelectorAll('[data-material-work]').forEach(group => {
      const row = rows().find(item => item.dataset.id === group.dataset.materialWork);
      group.hidden = !row?.querySelector('[name="trabalhos_ids"]').checked;
    });
    return data;
  }
  function message(text, extra, error = false) {
    status.textContent = text; detail.textContent = extra;
    status.classList.toggle('pf-live-error', error);
  }
  function save(action = 'auto') {
    clearTimeout(timer); sync();
    const body = new FormData(form), current = revision;
    body.set('acao', action);
    const task = queue.catch(() => {}).then(async () => {
      message(action === 'publicar' ? 'Publicando sua página…' : 'Salvando rascunho…', 'Aguarde a confirmação.');
      try {
        const response = await fetch(form.action || location.href, {method:'POST', body, headers:{'X-Requested-With':'XMLHttpRequest'}, credentials:'same-origin'});
        const result = await response.json().catch(() => ({}));
        if (!response.ok || !result.salvo) throw new Error(result.erro || 'Não foi possível salvar. Tente novamente.');
        if (current === revision) dirty = false;
        if (result.endereco_publico) form.dataset.publicUrl = result.endereco_publico;
        message(action === 'publicar' ? 'Página publicada' : dirty ? 'Alterações aguardando salvamento' : 'Rascunho salvo', action === 'publicar' ? result.endereco_publico : 'A versão pública só muda quando você publica.');
        preview.src = form.dataset.previewUrl + '?v=' + Date.now();
        return result;
      } catch (error) {
        dirty = true;
        message('Alterações ainda não salvas', error.message, true);
        throw error;
      }
    });
    queue = task;
    return task;
  }
  function changed() {
    dirty = true; revision++; sync();
    message('Alterações aguardando salvamento', 'Seu rascunho continua privado.');
    clearTimeout(timer); timer = setTimeout(() => save().catch(() => {}), 550);
  }
  const order = initial.pagina?.ordem_trabalhos || [];
  for (const id of order) { const row = rows().find(row => row.dataset.id === String(id)); if (row) row.parentNode.appendChild(row); }
  sync();
  form.addEventListener('input', changed);
  form.addEventListener('change', changed);
  form.addEventListener('click', event => {
    const button = event.target.closest('button');
    if (!button) return;
    if (button.dataset.destaque) {
      highlight = button.dataset.destaque;
      button.closest('.pf-work').querySelector('[name="trabalhos_ids"]').checked = true;
      changed();
    }
    if (button.dataset.mover) {
      const row = button.closest('.pf-work'), other = Number(button.dataset.mover) < 0 ? row.previousElementSibling : row.nextElementSibling;
      if (other) { Number(button.dataset.mover) < 0 ? other.before(row) : other.after(row); changed(); }
    }
  });
  form.addEventListener('submit', event => { event.preventDefault(); save(event.submitter?.value || 'salvar').catch(() => {}); });
  document.getElementById('portfolio-pdf').addEventListener('click', async event => {
    if (!dirty) return;
    event.preventDefault();
    try { await save(); location.assign(event.currentTarget?.href || document.getElementById('portfolio-pdf').href); } catch (_) {}
  });
  document.getElementById('portfolio-copiar').addEventListener('click', async () => {
    const data = sync().pagina, lines = [data.titulo, data.subtitulo, data.apresentacao, data.oferta];
    for (const row of rows()) if (row.querySelector('[name="trabalhos_ids"]').checked) {
      const work = data.legendas.find(item => item.peca_id === row.dataset.id);
      lines.push(work.titulo, work.texto);
    }
    if (form.dataset.publicUrl) lines.push('Portfólio: ' + form.dataset.publicUrl);
    const text = lines.filter(Boolean).join('\n\n');
    try { await navigator.clipboard.writeText(text); message('Apresentação copiada', 'Texto e endereço público, quando disponível.'); }
    catch (_) {
      const area = document.createElement('textarea'); area.value = text; area.setAttribute('aria-label','Texto da apresentação para copiar');
      area.style.cssText = 'position:fixed;inset:20%;z-index:30;width:60%;height:55%;background:white;color:#112c29;padding:1rem';
      const close = document.createElement('button'); close.textContent = 'Fechar texto'; close.type = 'button'; close.style.cssText = 'position:fixed;top:15%;right:20%;z-index:31';
      close.onclick = () => { area.remove(); close.remove(); }; document.body.append(area,close); area.select();
      message('Selecione e copie o texto', 'Seu navegador pediu cópia manual.');
    }
  });
  const aiButton = document.getElementById('portfolio-gerar-ia');
  const aiStatus = document.getElementById('portfolio-ia-status');
  aiButton?.addEventListener('click', async () => {
    sync();
    const texts = [...form.querySelectorAll('[name^="pagina_"], [name^="legenda_"]')];
    const values = new Map(texts.map(input => [input.name, input.value]));
    const body = new FormData(form);
    body.set('campo', 'completo');
    aiButton.disabled = true;
    aiStatus.textContent = 'O robô está escrevendo com base nos seus trabalhos…';
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 150000);
    try {
      const response = await fetch(form.dataset.aiUrl, {method:'POST', body, credentials:'same-origin', signal:controller.signal});
      const result = await response.json().catch(() => ({}));
      if (!response.ok || !result.conteudo?.pagina) throw new Error(result.erro || 'Não foi possível gerar agora. Tente novamente.');
      const generated = result.conteudo.pagina;
      const fields = ['titulo','subtitulo','apresentacao','oferta','continuidade','diferenciais','condicoes','duvidas','cta'];
      let kept = 0;
      for (const field of fields) {
        if (typeof generated[field] !== 'string') continue;
        const input = form.elements['pagina_' + field];
        if (input && input.value !== values.get(input.name)) { kept++; continue; }
        initial.pagina[field] = generated[field];
        if (input) input.value = generated[field];
      }
      for (const legend of generated.legendas || []) {
        for (const field of ['titulo', 'texto']) {
          const input = form.elements['legenda_' + field + '_' + legend.peca_id];
          if (!input || typeof legend[field] !== 'string') continue;
          if (input.value !== values.get(input.name)) { kept++; continue; }
          input.value = legend[field];
        }
      }
      changed();
      aiStatus.textContent = kept ? 'Textos gerados. Mantive os campos que você editou durante a geração.' : 'Textos gerados no rascunho. Revise e ajuste antes de publicar.';
    } catch (error) {
      aiStatus.textContent = error.name === 'AbortError' ? 'A geração demorou demais. Seus textos foram mantidos; tente novamente.' : error.name === 'TypeError' ? 'Não foi possível conectar ao robô. Seus textos foram mantidos; tente novamente.' : error.message;
    } finally {
      clearTimeout(timeout);
      aiButton.disabled = false;
    }
  });
  window.addEventListener('beforeunload', event => { if (dirty) { event.preventDefault(); event.returnValue = ''; } });
})();
