(()=>{'use strict';
const chat=document.querySelector('.sg-chat');if(!chat)return;
const textarea=chat.querySelector('#resposta'),form=chat.querySelector('[data-form-resposta]'),log=chat.querySelector('.historico-equipe'),contexto=chat.querySelector('#suporte-equipe-contexto'),status=chat.querySelector('#suporte-equipe-conexao');
for(const button of chat.querySelectorAll('[data-painel]'))button.addEventListener('click',()=>{chat.dataset.mobile=button.dataset.painel;for(const b of chat.querySelectorAll('[data-painel]'))b.classList.toggle('secondary',b!==button)});
const escolhasPendentes=new Set();for(const field of chat.querySelectorAll('[data-estado-select],[data-prioridade-select],[data-responsavel-select]'))field.addEventListener('change',()=>escolhasPendentes.add(field));
const key='meshcraft-suporte-rascunho:'+chat.dataset.rascunhoChave;
if(textarea&&chat.dataset.rascunhoChave){try{if(chat.dataset.enviado==='1'){sessionStorage.removeItem(key);textarea.value='';const clean=new URL(location.href);clean.searchParams.delete('enviado');history.replaceState(history.state,'',clean)}else{const saved=sessionStorage.getItem(key);if(saved!==null)textarea.value=saved}textarea.addEventListener('input',()=>sessionStorage.setItem(key,textarea.value));form?.addEventListener('submit',()=>sessionStorage.setItem(key,textarea.value))}catch(_){/* Armazenamento pode estar desativado. */}}
if(!log||!contexto||!status)return;log.scrollTop=log.scrollHeight;let ocupado=false;
async function atualizar(){if(ocupado||document.hidden)return;ocupado=true;try{
  const ids=[...log.querySelectorAll('[data-mensagem]')].map(e=>Number(e.dataset.mensagem));const url=new URL(location.href);url.search='';url.searchParams.set('formato','json');url.searchParams.set('depois',String(Math.max(0,...ids)));
  const response=await fetch(url,{credentials:'same-origin',cache:'no-store'});if(!response.ok)throw new Error('atualização indisponível');const data=await response.json();const c=data.conversa||{};const atBottom=log.scrollHeight-log.scrollTop-log.clientHeight<80;
  for(const m of c.mensagens||[]){if(ids.includes(Number(m.id)))continue;log.querySelector('[data-vazio]')?.remove();const a=document.createElement('article');a.className='sg-message '+(m.autor==='equipe'?'equipe':'');a.dataset.mensagem=m.id;const h=document.createElement('h3');h.textContent=(m.nome||m.autor)+' · '+new Date(m.em).toLocaleString('pt-BR');const p=document.createElement('p');p.textContent=m.texto;a.append(h,p);if(m.autor==='equipe'){const link=document.createElement('a');link.href=location.pathname.replace(/\/$/,'')+'/../base/?conversa='+encodeURIComponent(c.id)+'&mensagem='+encodeURIComponent(m.id);link.textContent='Guardar na base';a.append(link)}log.append(a)}
  if(atBottom)log.scrollTop=log.scrollHeight;
  if(data.contexto_em!==contexto.dataset.atualizado&&typeof data.contexto_html==='string'){const partial=contexto.querySelector('[data-contexto-parcial]');if(partial)partial.innerHTML=data.contexto_html;contexto.dataset.atualizado=data.contexto_em||''}
  const badge=chat.querySelector('[data-estado-badge]');if(badge&&c.estado){badge.className='sg-badge '+c.estado;badge.textContent=c.estado_nome||c.estado}
  const fields=[['[data-estado-select]',c.estado],['[data-prioridade-select]',c.prioridade],['[data-responsavel-select]',c.atendente_id]];for(const [selector,value] of fields){const field=chat.querySelector(selector);if(field&&value!==undefined&&field!==document.activeElement&&!escolhasPendentes.has(field))field.value=value||''}
  status.textContent='As novas mensagens aparecem automaticamente.';
}catch(_){status.textContent='Não foi possível atualizar agora. A resposta digitada continua no campo.'}finally{ocupado=false}}
setInterval(atualizar,5000);
})();
