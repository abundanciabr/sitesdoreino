(() => {
  'use strict';
  const grade = document.querySelector('#grade');
  if (!grade) return;
  const dialog = document.querySelector('#visualizador');
  const palco = document.querySelector('#palco');
  const grande = document.querySelector('#imagem-grande');
  const token = document.querySelector('#csrf-galeria').value;
  const pode = document.body.dataset.podeVotar === 'sim';
  let atual = '', zoom = 0, focoAnterior = null, avisoTimer;
  const cards = () => Array.from(grade.querySelectorAll('.modelo'));
  const cardAtual = () => cards().find(c => c.dataset.slug === atual);
  const aviso = (texto) => {
    const el = document.querySelector('#aviso'); el.textContent = texto; el.hidden = false;
    clearTimeout(avisoTimer); avisoTimer = setTimeout(() => { el.hidden = true; }, 6000);
  };
  const pedirEntrada = () => { aviso('Entre com sua conta de aluno com matrícula ativa para participar.'); };
  async function enviar(path, valores) {
    const resposta = await fetch(path, { method: 'POST', credentials: 'same-origin', headers: {'X-CSRFToken': token, 'Content-Type': 'application/x-www-form-urlencoded'}, body: new URLSearchParams(valores) });
    let dados;
    try { dados = await resposta.json(); } catch (_) { throw new Error('Não foi possível concluir agora. Recarregue a página e tente novamente.'); }
    if (!resposta.ok) throw new Error(dados.erro || 'Não foi possível concluir agora.');
    return dados;
  }
  function botaoVoto(botao, card) {
    const votado = card.dataset.votado === 'sim';
    botao.textContent = votado ? '♥ Retirar voto' : '♡ Votar';
    botao.classList.toggle('votado', votado); botao.setAttribute('aria-pressed', String(votado));
  }
  function atualizarModal() {
    const card = cardAtual(); if (!card) return;
    document.querySelector('#titulo-visualizador').textContent = card.dataset.titulo;
    document.querySelector('.contador-imagem').textContent = `${cards().indexOf(card) + 1} / ${cards().length}`;
    document.querySelector('#votos-modal').textContent = `${card.dataset.votos} voto${card.dataset.votos === '1' ? '' : 's'}`;
    botaoVoto(document.querySelector('#votar-modal'), card);
  }
  function ordenar(linhas) {
    linhas.forEach((linha, i) => {
      const card = cards().find(c => c.dataset.slug === linha.slug); if (!card) return;
      card.dataset.votos = String(linha.votos); card.dataset.votado = linha.votado ? 'sim' : 'nao';
      card.querySelector('.posicao').textContent = String(i + 1).padStart(2, '0');
      card.querySelector('.total-votos').textContent = `${linha.votos} voto${linha.votos === 1 ? '' : 's'}`;
      botaoVoto(card.querySelector('.votar'), card); grade.append(card);
    });
    if (dialog.open) atualizarModal();
  }
  const pendentes = new Set();
  async function votar(card) {
    if (!pode) { pedirEntrada(); return; }
    const slug = card.dataset.slug; if (pendentes.has(slug)) return;
    pendentes.add(slug); card.querySelector('.votar').disabled = true;
    if (atual === slug) document.querySelector('#votar-modal').disabled = true;
    const acao = card.dataset.votado === 'sim' ? 'retirar' : 'votar';
    try { const dados = await enviar('/comunidade/voto', { imagem: slug, acao }); ordenar(dados.imagens); aviso(acao === 'votar' ? 'Voto registrado.' : 'Voto retirado.'); }
    catch (erro) { aviso(erro.message); }
    finally { pendentes.delete(slug); card.querySelector('.votar').disabled = false; document.querySelector('#votar-modal').disabled = false; }
  }
  function mudarZoom(valor) {
    zoom = Math.min(4, Math.max(0, valor));
    palco.className = zoom === 0 ? 'palco fit' : `palco zoom-${zoom}`;
    document.querySelector('#zoom-texto').textContent = ['Ajustar', '150%', '200%', '300%', '400%'][zoom];
    document.querySelector('#menos').disabled = zoom === 0; document.querySelector('#mais').disabled = zoom === 4;
    if (zoom === 0) { palco.scrollTop = 0; palco.scrollLeft = 0; }
  }
  function mostrar(card) {
    atual = card.dataset.slug; grande.src = card.dataset.url; grande.alt = `Proposta ${card.dataset.titulo}`;
    mudarZoom(0); atualizarModal();
    const form = document.querySelector('#comentario-modal'); form.hidden = true; form.reset();
    form.dataset.chave = crypto.randomUUID(); form.querySelector('.retorno-comentario').textContent = '';
  }
  function abrir(card, foco) {
    focoAnterior = foco; mostrar(card); dialog.showModal(); document.body.classList.add('modal-aberto');
    document.querySelector('#fechar').focus();
  }
  function navegar(delta) { const lista = cards(); const indice = lista.findIndex(c => c.dataset.slug === atual); mostrar(lista[(indice + delta + lista.length) % lista.length]); }
  function fechar() { if (document.fullscreenElement === dialog) document.exitFullscreen().catch(() => {}); dialog.close(); }
  dialog.addEventListener('close', () => { document.body.classList.remove('modal-aberto'); if (focoAnterior) focoAnterior.focus(); });
  document.querySelector('#fechar').addEventListener('click', fechar);
  document.querySelector('#anterior').addEventListener('click', () => navegar(-1));
  document.querySelector('#proxima').addEventListener('click', () => navegar(1));
  document.querySelector('#mais').addEventListener('click', () => mudarZoom(zoom + 1));
  document.querySelector('#menos').addEventListener('click', () => mudarZoom(zoom - 1));
  document.querySelector('#ajustar').addEventListener('click', () => mudarZoom(0));
  document.querySelector('#tela-cheia').addEventListener('click', async () => {
    try { if (document.fullscreenElement) await document.exitFullscreen(); else if (dialog.requestFullscreen) await dialog.requestFullscreen(); }
    catch (_) { aviso('A imagem já está ampliada na tela.'); }
  });
  document.querySelector('#votar-modal').addEventListener('click', () => votar(cardAtual()));
  document.querySelector('#comentar-modal').addEventListener('click', () => { const form = document.querySelector('#comentario-modal'); form.hidden = !form.hidden; if (!form.hidden) form.querySelector('textarea').focus(); });
  dialog.addEventListener('keydown', e => {
    if (e.target.matches('textarea,input')) return;
    if (e.key === 'ArrowRight') { e.preventDefault(); navegar(1); }
    if (e.key === 'ArrowLeft') { e.preventDefault(); navegar(-1); }
    if (e.key === '+' || e.key === '=') { e.preventDefault(); mudarZoom(zoom + 1); }
    if (e.key === '-') { e.preventDefault(); mudarZoom(zoom - 1); }
    if (e.key === '0') mudarZoom(0);
  });
  palco.addEventListener('wheel', e => { if (e.ctrlKey) { e.preventDefault(); mudarZoom(zoom + (e.deltaY < 0 ? 1 : -1)); } }, { passive: false });
  palco.addEventListener('dblclick', () => mudarZoom(zoom ? 0 : 2));
  grande.draggable = false;
  let arrasto = null;
  palco.addEventListener('pointerdown', e => { if (!zoom || e.pointerType !== 'mouse' || e.button !== 0) return; arrasto = { x: e.clientX, y: e.clientY, left: palco.scrollLeft, top: palco.scrollTop }; palco.setPointerCapture(e.pointerId); palco.classList.add('arrastando'); });
  palco.addEventListener('pointermove', e => { if (!arrasto) return; palco.scrollLeft = arrasto.left - (e.clientX - arrasto.x); palco.scrollTop = arrasto.top - (e.clientY - arrasto.y); });
  const pararArrasto = () => { arrasto = null; palco.classList.remove('arrastando'); };
  palco.addEventListener('pointerup', pararArrasto); palco.addEventListener('pointercancel', pararArrasto);
  cards().forEach(card => {
    card.id = card.dataset.slug;
    card.querySelector('.abrir-imagem').addEventListener('click', e => abrir(card, e.currentTarget));
    card.querySelector('.votar').addEventListener('click', () => votar(card));
    card.querySelector('.form-comentario').dataset.chave = crypto.randomUUID();
  });
  document.querySelectorAll('.form-comentario').forEach(form => form.addEventListener('submit', async e => {
    e.preventDefault(); if (!pode) { pedirEntrada(); return; }
    const modal = form.id === 'comentario-modal'; const card = modal ? cardAtual() : form.closest('.modelo');
    const botao = form.querySelector('button'); if (botao.disabled) return;
    const texto = form.querySelector('textarea').value.trim(); if (!texto) return;
    botao.disabled = true;
    try {
      const dados = await enviar('/comunidade/comentario', { imagem: card.dataset.slug, texto, chave: form.dataset.chave });
      form.reset(); form.dataset.chave = dados.chave; form.querySelector('.retorno-comentario').textContent = dados.mensagem;
    } catch (erro) { form.querySelector('.retorno-comentario').textContent = erro.message; }
    finally { botao.disabled = false; }
  }));
})();
