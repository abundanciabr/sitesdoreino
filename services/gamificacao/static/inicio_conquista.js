'use strict';
window.iniciarConquista = (scope = document, host = {}) => {
  const link = scope.querySelector('.voltar-faixa');
  if (link) link.addEventListener('click', event => {
    const raw = scope.querySelector('#cerimonia-faixa-data');
    let progress; try { progress = JSON.parse(raw?.textContent || 'null'); } catch (_) {}
    if (progress?.celebracao?.ordem && window.MeshcraftFaixas) {
      event.preventDefault();
      window.MeshcraftFaixas.celebrar(progress, progress, {revelar: true,
        concluir: () => host.close ? host.close() : window.location.assign(link.href)});
    } else if (host.close) { event.preventDefault(); host.close(); }
  });
  const number = scope.getElementById('xp-numero');
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
};
window.iniciarConquista();
