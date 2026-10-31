(() => {
  'use strict';
  const form = document.querySelector('.busca-do-admin');
  if (!form) return;
  const input = form.querySelector('input[name="q"]');
  const painel = form.querySelector('.busca-sugestoes');
  const lista = form.querySelector('[role="listbox"]');
  const status = form.querySelector('[role="status"]');
  const todos = form.querySelector('.busca-ver-todos');
  let timer, controller, versao = 0, selecionado = -1;
  let opcoes = [];
  function fechar() {
    painel.hidden = true;
    input.setAttribute('aria-expanded', 'false');
    input.removeAttribute('aria-activedescendant');
    selecionado = -1;
  }
  function cancelar() {
    clearTimeout(timer);
    if (controller) controller.abort();
    versao++;
  }
  function abrir() {
    painel.hidden = false;
    input.setAttribute('aria-expanded', 'true');
  }
  function limpar() {
    lista.replaceChildren();
    opcoes = [];
    selecionado = -1;
    input.removeAttribute('aria-activedescendant');
  }
  async function sugerir(consulta, rodada) {
    controller = new AbortController();
    const url = new URL(form.dataset.sugestoes, location.origin);
    url.searchParams.set('q', consulta);
    try {
      const resposta = await fetch(url, {
        signal: controller.signal, credentials: 'same-origin', headers: {Accept: 'application/json'}
      });
      if (!resposta.ok) throw new Error('Sugestões indisponíveis');
      const dados = await resposta.json();
      if (rodada !== versao || input.value.trim() !== consulta || document.activeElement !== input) return;
      limpar();
      dados.resultados.forEach((pagina, i) => {
        const item = document.createElement('li');
        const link = document.createElement('a');
        const titulo = document.createElement('strong');
        const endereco = document.createElement('span');
        link.href = pagina.endereco;
        link.id = 'busca-opcao-' + i;
        link.setAttribute('role', 'option');
        link.setAttribute('aria-selected', 'false');
        titulo.textContent = pagina.titulo;
        endereco.textContent = 'meshcraft.top' + pagina.endereco;
        link.append(titulo, endereco);
        item.append(link);
        lista.append(item);
        opcoes.push(link);
      });
      status.textContent = dados.total ? dados.total + (dados.total === 1 ? ' página encontrada' : ' páginas encontradas') : 'Nenhuma página encontrada. Tente outro nome ou endereço.';
      todos.hidden = !dados.total;
      abrir();
    } catch (erro) {
      if (erro.name === 'AbortError' || rodada !== versao || document.activeElement !== input) return;
      limpar();
      status.textContent = 'Sugestões indisponíveis agora. Pressione Enter para pesquisar.';
      todos.hidden = true;
      abrir();
    }
  }
  input.addEventListener('input', () => {
    cancelar();
    limpar();
    const consulta = input.value.trim();
    if (!consulta) { fechar(); return; }
    const destino = new URL(form.action);
    destino.searchParams.set('q', consulta);
    todos.href = destino.href;
    todos.hidden = true;
    status.textContent = 'Buscando páginas…';
    abrir();
    const rodada = versao;
    timer = setTimeout(() => sugerir(consulta, rodada), 180);
  });
  input.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { cancelar(); fechar(); return; }
    if (painel.hidden) return;
    if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && opcoes.length) {
      event.preventDefault();
      selecionado = event.key === 'ArrowDown'
        ? (selecionado + 1) % opcoes.length
        : (selecionado <= 0 ? opcoes.length - 1 : selecionado - 1);
      opcoes.forEach((opcao, i) => opcao.setAttribute('aria-selected', String(i === selecionado)));
      input.setAttribute('aria-activedescendant', opcoes[selecionado].id);
      opcoes[selecionado].scrollIntoView({block: 'nearest'});
    } else if (event.key === 'Enter' && selecionado >= 0) {
      event.preventDefault();
      location.assign(opcoes[selecionado].href);
    }
  });
  form.addEventListener('submit', () => { cancelar(); fechar(); });
  document.addEventListener('click', (event) => {
    if (!form.contains(event.target)) { cancelar(); fechar(); }
  });
  form.addEventListener('focusout', () => {
    setTimeout(() => { if (!form.contains(document.activeElement)) { cancelar(); fechar(); } }, 0);
  });
})();
