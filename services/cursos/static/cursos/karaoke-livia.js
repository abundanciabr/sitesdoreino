(() => {
  'use strict';
  document.querySelectorAll('.karaoke-livia').forEach(async root => {
    const video = root.querySelector('video');
    const palco = root.querySelector('.karaoke-palco');
    const legenda = root.querySelector('.karaoke-legenda');
    const leitura = root.querySelector('.karaoke-leitura');
    const seguinte = root.querySelector('.karaoke-seguinte');
    const status = root.querySelector('.karaoke-status');
    const range = root.querySelector('input[type="range"]');
    const tempo = root.querySelector('output');
    const play = root.querySelector('[data-acao="play"]');
    const bloco = root.querySelector('[data-ajuste="bloco"]');
    let data, index = -1, activeWord = -2, stopAt = null;
    const clock = t => `${Math.floor(t / 60)}:${String(Math.floor(t % 60)).padStart(2, '0')}`;
    const spans = [];
    function render() {
      const t = video.currentTime;
      if (stopAt !== null && t >= stopAt) {
        video.pause();
        stopAt = null;
      }
      // The video's playhead is the sole clock: seeking, pauses and speed changes stay in sync.
      const found = data.frases.findIndex(f => t >= f.inicio && t < f.fim);
      const pause = data.pausas.find(p => t >= p.inicio && t < p.fim);
      if (found !== index) {
        index = found;
        activeWord = -2;
        spans.length = 0;
        legenda.replaceChildren();
        leitura.replaceChildren();
        if (index >= 0) {
          const f = data.frases[index];
          f.palavras.forEach(w => {
            const onVideo = document.createElement('span');
            const below = document.createElement('span');
            onVideo.textContent = below.textContent = w.texto + ' ';
            legenda.append(onVideo);
            leitura.append(below);
            spans.push([onVideo, below]);
          });
          seguinte.textContent = data.frases[index + 1] ? 'A seguir: ' + data.frases[index + 1].texto : 'Última frase do ensaio.';
        }
      }
      if (index >= 0) {
        const word = data.frases[index].palavras.findIndex(w => t >= w.inicio && t < w.fim);
        if (word !== activeWord) {
          activeWord = word;
          spans.forEach((pair, i) => pair.forEach(el => {
            el.classList.toggle('palavra-atual', i === word);
            el.classList.toggle('palavra-lida', word >= 0 && i < word);
          }));
        }
      } else {
        const message = pause ? pause.texto : t >= data.duracao ? 'Ensaio concluído. Guarde o áudio e os takes.' : 'Prepare-se para a próxima fala.';
        legenda.textContent = leitura.textContent = message;
        const next = data.frases.find(f => f.inicio >= t);
        seguinte.textContent = next ? 'A seguir: ' + next.texto : '';
      }
      const b = data.blocos.find(b => t >= b.inicio && t < b.fim) || data.blocos.at(-1);
      status.textContent = `Bloco ${b.numero} de 5 · ${video.paused ? 'Pausado' : 'Leia a palavra em verde'}${pause ? ' · Pausa da prática' : ''}`;
      bloco.value = String(b.inicio);
      tempo.textContent = `${clock(t)} / ${clock(data.duracao)}`;
      if (document.activeElement !== range) range.value = t;
      play.textContent = video.paused ? (t === 0 ? 'Iniciar ensaio' : 'Continuar ensaio') : 'Pausar ensaio';
      root.querySelector('[data-acao="anterior"]').disabled = index === 0 && t === 0;
    }
    function currentIndex() {
      return index >= 0 ? index : Math.max(0, data.frases.findLastIndex(f => f.inicio <= video.currentTime));
    }
    function seek(t) { stopAt = null; video.pause(); video.currentTime = t; render(); }
    async function start() {
      try { await video.play(); } catch (_) { status.textContent = 'Não foi possível tocar. Tente Iniciar ensaio novamente.'; }
    }
    try {
      const url = new URL(root.dataset.roteiro, window.location.href);
      if (url.origin !== window.location.origin) throw new Error('origem');
      const response = await fetch(url, { credentials: 'same-origin' });
      if (!response.ok) throw new Error('roteiro');
      data = await response.json();
      if (!data.frases?.length) throw new Error('frases');
      range.max = data.duracao;
      root.querySelectorAll('button,select,input').forEach(el => { el.disabled = false; });
      video.controls = false;
      legenda.hidden = false;
      render();
    } catch (_) {
      status.textContent = 'As falas não carregaram. Reabra a página ou baixe o vídeo com karaokê abaixo.';
      return;
    }
    root.addEventListener('click', async event => {
      const action = event.target.closest('[data-acao]')?.dataset.acao;
      if (!action) return;
      const i = currentIndex();
      if (action === 'play') { stopAt = null; if (video.ended) video.currentTime = 0; video.paused ? await start() : video.pause(); }
      if (action === 'anterior') seek(data.frases[Math.max(0, i - 1)].inicio);
      if (action === 'proxima') seek(data.frases[Math.min(data.frases.length - 1, i + 1)].inicio);
      if (action === 'reiniciar') seek(0);
      if (action === 'repetir') { seek(data.frases[i].inicio); stopAt = data.frases[i].fim; await start(); }
      if (action === 'tela') {
        try { document.fullscreenElement ? await document.exitFullscreen() : await palco.requestFullscreen(); }
        catch (_) { status.textContent = 'Seu navegador não abriu a tela cheia. Use o vídeo baixado para ler em tela cheia.'; }
      }
      render();
    });
    bloco.addEventListener('change', () => seek(Number(bloco.value)));
    root.querySelector('[data-ajuste="ritmo"]').addEventListener('change', event => { video.playbackRate = Number(event.target.value); render(); });
    range.addEventListener('input', () => seek(Number(range.value)));
    ['timeupdate','seeking','seeked','play','pause','ended','loadedmetadata'].forEach(name => video.addEventListener(name, render));
    video.addEventListener('error', () => { status.textContent = 'O vídeo não carregou. Reabra a página ou use o arquivo para baixar.'; });
    function frame() {
      if (!video.paused) render();
      if ('requestVideoFrameCallback' in video) video.requestVideoFrameCallback(frame);
      else requestAnimationFrame(frame);
    }
    frame();
  });
})();
