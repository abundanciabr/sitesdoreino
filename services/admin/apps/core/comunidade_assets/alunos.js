(() => {
  'use strict';
  const form = document.getElementById('form-busca-alunos');
  const busca = document.getElementById('buscar-aluno');
  const resultados = document.getElementById('resultados-alunos');
  if (!form || !busca || !resultados) return;
  let atraso, controlador, versao = 0;
  function limpar() {
    clearTimeout(atraso);
    if (controlador) controlador.abort();
    versao++;
    resultados.replaceChildren();
    resultados.hidden = true;
    resultados.removeAttribute('aria-busy');
  }
  async function pesquisar() {
    limpar();
    const termo = busca.value.trim();
    if (!termo) return;
    const atual = versao;
    controlador = new AbortController();
    resultados.setAttribute('aria-busy', 'true');
    try {
      const url = new URL(form.action);
      url.searchParams.set('q', termo);
      const resposta = await fetch(url, {signal:controlador.signal, credentials:'same-origin', cache:'no-store'});
      const html = await resposta.text();
      if (atual !== versao) return;
      const pagina = new DOMParser().parseFromString(html, 'text/html');
      const lista = pagina.getElementById('resultados-alunos');
      if (!lista) throw new Error();
      resultados.replaceChildren(...Array.from(lista.childNodes));
      resultados.hidden = false;
    } catch (erro) {
      if (atual !== versao || erro.name === 'AbortError') return;
      const aviso = document.createElement('p');
      aviso.className = 'estado-vazio';
      aviso.setAttribute('role', 'status');
      aviso.textContent = 'Não foi possível buscar agora. Tente novamente.';
      resultados.replaceChildren(aviso);
      resultados.hidden = false;
    } finally {
      if (atual === versao) resultados.removeAttribute('aria-busy');
    }
  }
  busca.addEventListener('input', () => {
    limpar();
    if (busca.value.trim()) atraso = setTimeout(pesquisar, 350);
  });
  form.addEventListener('submit', evento => { evento.preventDefault(); pesquisar(); });
})();
