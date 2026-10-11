(() => {
  'use strict';
  if (document.body.dataset.embutido === 'sim' && window.parent !== window) {
    const close = () => window.parent.postMessage({type: 'meshcraft:motivo-fechar'}, window.location.origin);
    document.querySelector('.voltar-faixa').addEventListener('click', event => { event.preventDefault(); close(); });
    window.addEventListener('message', event => {
      if (event.origin === window.location.origin && event.source === window.parent && event.data?.type === 'meshcraft:motivo-pedir-fechamento') close();
    });
    window.parent.postMessage({type: 'meshcraft:motivo-pronto'}, window.location.origin);
  }
  const number = document.getElementById('xp-numero');
  if (!number || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
  const total = Number(number.dataset.xp);
  if (!Number.isSafeInteger(total) || total < 1) return;
  const start = performance.now();
  const duration = 750;
  const frame = now => {
    const progress = Math.min(1, (now - start) / duration);
    number.textContent = Math.round(total * (1 - (1 - progress) ** 3)).toLocaleString('pt-BR');
    if (progress < 1) requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
})();
