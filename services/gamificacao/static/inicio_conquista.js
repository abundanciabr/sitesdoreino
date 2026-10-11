(() => {
  'use strict';
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
