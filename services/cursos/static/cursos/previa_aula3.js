const video = document.getElementById('video-aula3');
const chapters = [...document.querySelectorAll('[data-video-inicio]')];
chapters.forEach(button => button.addEventListener('click', () => {
  const seek = () => { video.currentTime = Number(button.dataset.videoInicio.replace(',', '.')); video.play().catch(() => video.focus()); };
  if (video.readyState) seek(); else video.addEventListener('loadedmetadata', seek, { once: true });
  video.scrollIntoView({ behavior: 'smooth', block: 'center' });
}));
video.addEventListener('timeupdate', () => {
  const current = chapters.filter(b => Number(b.dataset.videoInicio.replace(',', '.')) <= video.currentTime).at(-1);
  chapters.forEach(b => b.setAttribute('aria-current', String(b === current)));
});
