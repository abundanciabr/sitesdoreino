(() => {
  'use strict';
  const caixa = document.querySelector('[data-seguidores]');
  if (!caixa) return;
  const resumo = caixa.querySelector('.seguidores-resumo');
  const itens = caixa.querySelector('.seguidores-itens');
  const retorno = caixa.querySelector('.seguidores-retorno');
  let ultimaLista = '', consultando = false;
  const csrf = () => caixa.querySelector('[name=csrfmiddlewaretoken]').value;
  function estadoBotao(alvo, rotulo) {
    document.querySelectorAll('[data-seguir]').forEach(b => {
      if (b.dataset.seguir === alvo) { b.textContent = rotulo; b.disabled = true; }
    });
  }
  function mostrar(dados) {
    (dados.enviados || []).forEach(p => estadoBotao(p.alvo, p.rotulo));
    const assinatura = JSON.stringify(dados.recebidos);
    resumo.textContent = dados.pendentes ? `${dados.pendentes} ${dados.pendentes === 1 ? 'solicitação' : 'solicitações'} para seguir você.` : 'Nenhuma solicitação aguardando sua resposta.';
    if (assinatura === ultimaLista) return;
    ultimaLista = assinatura; itens.replaceChildren();
    for (const pedido of dados.recebidos || []) {
      const item = document.createElement('article'); item.className = 'seguidores-item';
      const nome = document.createElement('strong'); nome.textContent = pedido.nome + ' (@' + pedido.usuario + ')'; item.append(nome);
      const texto = document.createElement('p');
      texto.textContent = pedido.estado === 'pendente' ? 'Quer seguir você. Você aceita esse novo seguidor?' : pedido.estado === 'aceito' ? 'Agora segue você.' : 'Solicitação recusada.';
      item.append(texto);
      if (pedido.estado === 'pendente') {
        const acoes = document.createElement('div'); acoes.className = 'seguidores-acoes';
        for (const [acao, rotulo] of [['aceitar','Aceitar'],['recusar','Recusar']]) {
          const b = document.createElement('button'); b.type = 'button'; b.textContent = rotulo; b.className = acao;
          b.setAttribute('aria-label', rotulo + ' seguidor ' + pedido.nome);
          b.addEventListener('click', async () => {
            acoes.querySelectorAll('button').forEach(x => x.disabled = true);
            try { const d = await enviar('/comunidade/seguidores/responder', {pedido:pedido.id, acao}); mostrar(d); retorno.textContent = acao === 'aceitar' ? 'Seguidor aceito.' : 'Solicitação recusada.'; }
            catch (e) { retorno.textContent = e.message; acoes.querySelectorAll('button').forEach(x => x.disabled = false); }
          });
          acoes.append(b);
        }
        item.append(acoes);
      }
      itens.append(item);
    }
  }
  async function enviar(url, valores) {
    const corpo = new FormData(); Object.entries(valores).forEach(([k,v]) => corpo.append(k,v)); corpo.append('csrfmiddlewaretoken', csrf());
    const r = await fetch(url, {method:'POST',body:corpo,credentials:'same-origin'});
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.erro || 'Não foi possível salvar. Atualize a página e tente novamente.');
    return d;
  }
  async function atualizar() {
    if (consultando || document.hidden) return;
    consultando = true;
    try { const r = await fetch('/comunidade/seguidores', {cache:'no-store',credentials:'same-origin'}); if (!r.ok) throw new Error(); mostrar(await r.json()); }
    catch (_) { retorno.textContent = 'Não foi possível atualizar os avisos agora. Tente novamente.'; }
    finally { consultando = false; }
  }
  document.querySelectorAll('.seguir-form').forEach(form => form.addEventListener('submit', async e => {
    e.preventDefault(); const b = form.querySelector('button'); if (b.disabled) return;
    let aviso = form.querySelector('.seguir-retorno'); if (!aviso) { aviso = document.createElement('p'); aviso.className = 'seguir-retorno'; aviso.setAttribute('role','status'); form.append(aviso); } aviso.textContent = '';
    b.disabled = true; const alvo = form.querySelector('[name=alvo]').value;
    try { const d = await enviar(form.action, {alvo}); estadoBotao(alvo, d.rotulo); aviso.textContent = d.criado ? 'Aguardando aceite.' : d.rotulo; retorno.textContent = d.criado ? 'Solicitação enviada. A pessoa será avisada na comunidade para aceitar ou recusar.' : d.rotulo; }
    catch (erro) { b.disabled = false; aviso.textContent = erro.message; retorno.textContent = erro.message; }
  }));
  caixa.querySelector('.seguidores-atualizar').addEventListener('click', atualizar);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) atualizar(); });
  atualizar(); setInterval(atualizar, 20000);
})();
