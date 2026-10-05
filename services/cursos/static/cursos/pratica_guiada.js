/* A prática usa o mesmo documento da aula, sem página incorporada. */
(() => {
  const root = document.getElementById('pratica-interativa');
  if (!root) return;
  const data = JSON.parse(document.getElementById('dados-pratica').textContent);
  const base = root.dataset.base, steps = data.steps;
  const $ = name => root.querySelector(`[data-pratica="${name}"]`);
  let step = 0, complete = false, busy = false;
  const prepared = new Map();
  function prepare(file) {
    if (!prepared.has(file)) {
      const img = new Image();
      img.decoding = 'async'; img.src = base + file;
      prepared.set(file, img.decode().catch(error => { prepared.delete(file); throw error; }));
    }
    return prepared.get(file);
  }
  function reserve() {
    const values = {
      title: [...steps.map(s => s.title), data.final.title],
      instruction: [...steps.map(s => s.text), data.final.text],
      counter: ['Etapa 2 de 5 · partes e materiais', 'Prática concluída · 5 etapas'],
      feedback: [...steps.map(s => s.reply), ...steps.map(s => 'Clique na área marcada da imagem. ' + s.text), 'A imagem não carregou. Clique em Avançar para tentar novamente.']
    };
    for (const [name, texts] of Object.entries(values)) {
      const el = $(name), measure = document.createElement(el.tagName);
      measure.className = el.className;
      measure.style.cssText = `position:absolute;visibility:hidden;pointer-events:none;width:${el.getBoundingClientRect().width}px`;
      el.parentNode.appendChild(measure);
      let height = 0;
      for (const text of texts) { measure.textContent = text; height = Math.max(height, measure.getBoundingClientRect().height); }
      measure.remove(); el.style.minHeight = height + 'px';
    }
  }
  function render(reply = '') {
    const s = complete ? data.final : steps[step];
    $('counter').textContent = complete ? 'Prática concluída · 5 etapas' : `Etapa ${s.stage} de 5${data.width === 1366 && s.stage === 2 ? ' · partes e materiais' : ''}`;
    $('progress').value = complete ? 5 : s.stage - 1;
    $('title').textContent = s.title; $('instruction').textContent = s.text;
    $('screen').src = base + s.image; $('screen').alt = s.title + ' — captura real do Blender em português';
    $('target').hidden = complete; $('target').disabled = busy || complete;
    if (!complete) {
      const [x, y] = s.point;
      Object.assign($('target').style, {left: x / data.width * 100 + '%', top: y / data.height * 100 + '%'});
      $('target').dataset.side = x > data.width / 2 ? 'right' : 'left';
      $('target').setAttribute('aria-label', s.text); $('number').textContent = s.stage;
    }
    $('feedback').textContent = reply;
    $('back').disabled = busy || (!complete && step === 0);
    $('next').disabled = busy || complete;
    $('next').textContent = complete ? 'Prática concluída' : step === steps.length - 1 ? 'Concluir prática' : 'Avançar';
    $('restart').disabled = busy;
  }
  async function move(action) {
    if (busy || (complete && action === 'next')) return;
    const nextStep = action === 'restart' ? 0 : action === 'back' ? (complete ? step : Math.max(0, step - 1)) : Math.min(step + 1, steps.length - 1);
    const finish = action === 'next' && step === steps.length - 1;
    const reply = action === 'next' ? steps[step].reply : '';
    busy = true;
    for (const name of ['target', 'back', 'next', 'restart']) $(name).disabled = true;
    try {
      await prepare(finish ? data.final.image : steps[nextStep].image);
      step = nextStep; complete = finish;
      busy = false; render(reply);
    } catch (error) {
      busy = false; render('A imagem não carregou. Clique em Avançar para tentar novamente.');
    }
  }
  $('target').addEventListener('click', event => { event.stopPropagation(); move('next'); });
  $('stage').addEventListener('click', () => { if (!complete && !busy) $('feedback').textContent = 'Clique na área marcada da imagem. ' + steps[step].text; });
  for (const action of ['next', 'back', 'restart']) $(action).addEventListener('click', () => move(action));
  render(); reserve();
  new ResizeObserver(reserve).observe($('stage'));
  for (const file of new Set([...steps.map(s => s.image), data.final.image])) prepare(file).catch(() => {});
})();
