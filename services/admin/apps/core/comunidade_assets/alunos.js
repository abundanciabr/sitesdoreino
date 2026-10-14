(() => {
  'use strict';
  const busca = document.getElementById('buscar-aluno');
  if (!busca) return;
  const normalizar = texto => texto.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
  busca.addEventListener('input', () => {
    const termo = normalizar(busca.value).replace(/^@/, '');
    let total = 0;
    document.querySelectorAll('[data-busca]').forEach(linha => {
      linha.hidden = !normalizar(linha.dataset.busca).includes(termo);
      if (!linha.hidden) total++;
    });
    document.getElementById('busca-vazia').hidden = total > 0;
  });
})();
