(() => {
  'use strict';
  const form = document.getElementById('form-perfil');
  if (form) {
    const imagem = document.getElementById('foto-preview');
    const foto = document.getElementById('foto');
    let objeto;
    form.querySelectorAll('input[name="avatar"]').forEach(radio => radio.addEventListener('change', () => {
      if (objeto) URL.revokeObjectURL(objeto);
      foto.value = '';
      imagem.src = '/comunidade/avatar/' + radio.value;
    }));
    foto.addEventListener('change', () => {
      if (!foto.files.length) return;
      if (objeto) URL.revokeObjectURL(objeto);
      objeto = URL.createObjectURL(foto.files[0]); imagem.src = objeto;
      form.querySelectorAll('input[name="avatar"]').forEach(radio => {radio.checked = false;});
    });
    const usuario = document.getElementById('usuario'), status = document.getElementById('disponibilidade');
    let atraso, controlador;
    usuario.addEventListener('input', () => {
      clearTimeout(atraso); if (controlador) controlador.abort(); status.textContent = '';
      const nome = usuario.value.trim().replace(/^@/, '').toLowerCase();
      if (!nome) return;
      atraso = setTimeout(async () => {
        controlador = new AbortController();
        try {
          const r = await fetch('/comunidade/disponivel?usuario=' + encodeURIComponent(nome), {signal: controlador.signal});
          if (!r.ok) return;
          const dado = await r.json(); status.textContent = dado.disponivel ? 'Esse @ está disponível.' : 'Escolha outro @: esse nome está em uso ou não está no formato indicado.';
        } catch (_) {}
      }, 350);
    });
  }
  const tema = document.getElementById('tema');
  if (tema) tema.addEventListener('change', () => {document.body.dataset.tema = tema.value;});
  const busca = document.getElementById('buscar-aluno');
  if (busca) busca.addEventListener('input', () => {
    const termo = busca.value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();
    let total = 0;
    document.querySelectorAll('[data-busca]').forEach(linha => {
      const texto = linha.dataset.busca.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
      linha.hidden = !texto.includes(termo); if (!linha.hidden) total++;
    });
    document.getElementById('busca-vazia').hidden = total > 0;
  });
})();
