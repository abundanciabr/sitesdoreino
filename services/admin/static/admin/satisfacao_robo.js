(() => {
  const bloco = document.querySelector('[data-satisfacao-andamento]');
  if (!bloco) return;
  const url = new URL(bloco.dataset.satisfacaoAndamento, window.location.origin);
  url.searchParams.set('site_id', bloco.dataset.site);
  url.searchParams.set('aluno_id', bloco.dataset.aluno);
  url.searchParams.set('avaliacao', bloco.dataset.avaliacao);
  async function conferir() {
    try {
      const resposta = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
      if (resposta.ok && (await resposta.json()).marca !== bloco.dataset.marca) {
        window.location.reload();
        return;
      }
    } catch (_) { /* A execução segue no servidor; a próxima consulta retoma a tela. */ }
    window.setTimeout(conferir, 5000);
  }
  window.setTimeout(conferir, 5000);
})();
