'use strict';
(async () => {
  const root = document.getElementById('ciclo-criacao'); if (!root) return;
  const form = document.getElementById('ciclo-form'), status = document.getElementById('ciclo-status');
  let data, busy = false;
  async function request(body) {
    const response = await fetch(root.dataset.api, {method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: body ? {'X-CSRFToken': data.csrf} : {}, ...(body ? {body} : {})});
    const result = await response.json(); if (!response.ok) throw new Error(result.detail || 'Não foi possível avaliar agora.');
    if (data && (data.pessoa_id !== result.pessoa_id || data.site_id !== result.site_id)) { form.hidden = true; throw new Error('Sua sessão mudou. Entre novamente.'); }
    return result;
  }
  try { data = await request(); } catch (error) { status.textContent = error.message; form.hidden = true; return; }
  const latest = data.avaliacoes.find(a => a.ordem === Number(root.dataset.ordem));
  if (latest) status.textContent = latest.feedback;
  form.addEventListener('submit', async event => {
    event.preventDefault(); if (busy) return;
    const body = new FormData(form); body.set('acao', 'ciclo-avaliar'); body.set('ordem', root.dataset.ordem);
    body.set('revisao', String(data.revisao)); body.set('contexto_pessoa', data.pessoa_id); body.set('contexto_site', data.site_id);
    busy = true; form.querySelector('button').disabled = true; status.textContent = 'Avaliando o material apresentado…';
    try { data = await request(body); const result = data.avaliacao_atual;
      status.textContent = result?.feedback || 'Material guardado. A avaliação continua pendente.';
      if (result?.conquistada) status.textContent += ` Faixa ${data.faixa_nome} conquistada.${result.bonus_xp ? ` +${result.bonus_xp.toLocaleString('pt-BR')} XP.` : ' Os bônus já recebidos ficam preservados.'}`;
    } catch (error) { status.textContent = error.message; try { data = await request(); } catch (_) {} }
    finally { busy = false; form.querySelector('button').disabled = false; }
  });
})();
