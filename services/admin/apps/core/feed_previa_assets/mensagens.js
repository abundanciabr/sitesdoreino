(() => {
  'use strict';
  const $=id=>document.getElementById(id), urls=document.body.dataset;
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const avatar=p=>`<span class="avatar ${esc(p.color)}">${esc(p.initials)}</span>`;
  let inbox={conversations:[],unread:0,latest:0}, selected=null, recipients=[], visitor=false;
  let source=null, reconnect=null, poll=null, failures=0, loaded=false, sending=false, starting=false, reading=false, readAgain=false;
  const chats=new Map(), drafts=new Map(), retries=new Map();
  const dialog=$('messages-dialog'), history=$('message-history'), input=$('message-text');
  async function request(url,data){
    const r=await fetch(url,{credentials:'same-origin',method:data?'POST':'GET',headers:data?{'Content-Type':'application/json','X-CSRFToken':document.querySelector('[name=csrfmiddlewaretoken]').value}:{},body:data?JSON.stringify(data):undefined});
    let result;try{result=await r.json();}catch{throw Error(`A conexão com as mensagens falhou (HTTP ${r.status}). Atualize a prévia e tente novamente.`);}
    if(!r.ok)throw Error(result.error||'Não foi possível abrir esta conversa privada.');return result;
  }
  function toast(text){$('toast').textContent=text;$('toast').classList.add('visible');clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').classList.remove('visible'),4500);}
  function status(text,live=false){$('message-connection').textContent=text;$('message-connection').className=live?'notification-live':'notification-reconnecting';}
  const endpoint=id=>urls.messages+'conversa/'+encodeURIComponent(id)+'/';
  const atBottom=()=>history.scrollHeight-history.scrollTop-history.clientHeight<65;
  function drawInbox(){
    const count=inbox.unread;$('message-count').hidden=!count;$('message-count').textContent=count>99?'99+':String(count);
    $('message-bell').classList.toggle('has-unread',count>0);$('message-bell').setAttribute('aria-label',`Abrir mensagens privadas${count?`, ${count} não lidas`:''}`);
    const q=$('message-search').value.toLowerCase(), items=inbox.conversations.filter(c=>[c.peer.name,c.peer.handle].join(' ').toLowerCase().includes(q));
    $('message-conversations').innerHTML=items.length?items.map(c=>`<button class="dm-conversation ${selected===c.id?'selected':''}" data-message-conversation="${esc(c.id)}">${avatar(c.peer)}<span><b>${esc(c.peer.name)}</b><small>${c.last_demo?'Simulação · ':c.last_mine?'Você: ':''}${esc(c.last)}</small><em>${c.peer.demo?'Perfil fictício':'Admin da prévia'}</em></span>${c.unread?`<strong class="dm-unread">${c.unread}</strong>`:''}</button>`).join(''):'<div class="dm-empty">Nenhuma conversa encontrada.<br>Comece pelo perfil de um criador ou em Nova conversa.</div>';
  }
  function mergeChat(data,older=false){
    let chat=chats.get(data.id);
    if(!chat){chat={...data,messages:[]};chats.set(data.id,chat);}
    const merged=new Map(chat.messages.map(m=>[m.id,m]));data.messages.forEach(m=>merged.set(m.id,m));chat.messages=[...merged.values()].sort((a,b)=>a.id-b.id);chat.peer=data.peer;
    if(older||chat.messages.length===data.messages.length)chat.has_more=data.has_more;
    return chat;
  }
  function drawChat(forceBottom=false,prepend=false){
    const chat=chats.get(selected);$('message-picker').hidden=true;$('message-chat').hidden=false;
    if(!chat){$('message-peer').innerHTML='';history.innerHTML='<div class="dm-welcome"><span>✉</span><h3>Uma boa conversa começa com uma ideia.</h3><p>Troque experiências sobre criações, evolução e portfólio em um espaço privado.</p><button class="primary" data-message-new>Começar uma conversa →</button></div>';$('message-form').hidden=true;$('message-demo').hidden=true;return;}
    const near=forceBottom||atBottom(), previous=history.scrollHeight, top=history.scrollTop;
    $('message-peer').innerHTML=`${avatar(chat.peer)}<div><b>${esc(chat.peer.name)}</b><small>@${esc(chat.peer.handle)} · ${chat.peer.demo?'Perfil fictício':'Admin da prévia'}</small></div><span>◈ Privada</span>`;
    const html=(chat.has_more?'<button class="textbtn dm-older" data-message-older>Carregar mensagens anteriores ↑</button>':'')+(chat.messages.length?chat.messages.map(m=>`<article class="dm-bubble ${m.mine?'mine':'received'}" data-message-id="${m.id}">${m.demo?'<strong class="dm-simulation">Resposta simulada · perfil fictício</strong>':''}<p>${esc(m.text).replace(/\n/g,'<br>')}</p><small>${esc(m.time)}${m.mine?` · ${m.read?'✓✓ Lida':'✓ Enviada'}`:''}</small></article>`).join(''):'<div class="dm-empty">Sua primeira mensagem começa esta conversa.</div>');
    if(history.innerHTML!==html){history.innerHTML=html;if(near&&!prepend)history.scrollTop=history.scrollHeight;else history.scrollTop=top+(prepend?Math.max(0,history.scrollHeight-previous):0);}
    if(forceBottom&&!prepend)history.scrollTop=history.scrollHeight;
    $('message-form').hidden=false;$('message-demo').hidden=!chat.peer.demo;
    $('message-send').disabled=sending;markRead();
  }
  function accept(data,announce=false){
    const previous=inbox.latest;inbox=data;drawInbox();
    if(data.chat){mergeChat(data.chat);if(selected===data.chat.id&&dialog.open)drawChat();}
    if(announce&&loaded&&!visitor){const fresh=data.conversations.filter(c=>c.last_id>previous&&!c.last_mine&&c.unread);if(fresh.length)toast(`Nova mensagem privada de ${fresh[0].peer.name}${fresh[0].last_demo?' · resposta simulada':''}.`);}
    loaded=true;
  }
  async function markRead(){
    if(!selected||!dialog.open||document.visibilityState==='hidden'||!atBottom())return;
    const chat=chats.get(selected), pending=chat?.messages.filter(m=>!m.mine&&!m.read);if(!pending?.length)return;
    if(reading){readAgain=true;return;}reading=true;const id=selected;
    const cutoff=pending.at(-1).id;
    try{const data=await request(urls.messageRead,{conversation:id,before:cutoff});chats.get(id)?.messages.forEach(m=>{if(!m.mine&&m.id<=cutoff)m.read=true;});accept(data);}catch(e){$('message-error').textContent=e.message;}finally{reading=false;if(readAgain){readAgain=false;markRead();}}
  }
  function stop(){source?.close();source=null;clearTimeout(reconnect);reconnect=null;clearInterval(poll);poll=null;failures=0;}
  async function refresh(){const data=await request(urls.messages);if(selected){data.chat=await request(endpoint(selected));}if(!visitor)accept(data,true);}
  function fallback(){if(poll)return;poll=setInterval(()=>refresh().catch(()=>status('Conexão indisponível · tentando novamente')),5000);}
  function connect(){
    if(visitor||source)return;if(typeof EventSource==='undefined'){fallback();return;}
    const active=new EventSource(urls.messageStream+(selected?'?conversation='+encodeURIComponent(selected):''));source=active;
    active.addEventListener('messages',e=>{if(source!==active||visitor)return;try{accept(JSON.parse(e.data),true);failures=0;clearInterval(poll);poll=null;status('Ao vivo',true);}catch{status('Reconectando mensagens…');fallback();}});
    active.onerror=()=>{if(source!==active)return;active.close();source=null;status('Reconectando mensagens…');if(++failures>=2)fallback();clearTimeout(reconnect);reconnect=setTimeout(()=>{reconnect=null;connect();},2000);};
  }
  function restart(){stop();status('Conectando…');connect();}
  async function choose(id){
    drafts.set(selected,input.value);selected=id;input.value=drafts.get(id)||'';$('message-error').textContent='';
    try{const chat=await request(endpoint(id));if(selected!==id||visitor)return;mergeChat(chat);drawInbox();drawChat(true);restart();input.focus();}catch(e){$('message-error').textContent=e.message;toast(e.message);}
  }
  async function open(){
    if(visitor)return;document.querySelectorAll('dialog[open]').forEach(d=>{if(d!==dialog)d.close();});if(!dialog.open)dialog.showModal();drawInbox();drawChat();
    try{await refresh();}catch(e){toast(e.message);}connect();
  }
  async function start(key){
    if(visitor||starting)return;starting=true;
    try{const data=await request(urls.messageStart,{profile:key});if(visitor)return;selected=data.chat.id;input.value=drafts.get(selected)||'';$('message-error').textContent='';mergeChat(data.chat);accept(data);drawChat(true);restart();input.focus();}catch(e){toast(e.message);}finally{starting=false;}
  }
  function drawRecipients(){
    const q=$('message-recipient-search').value.toLowerCase();$('message-recipients').innerHTML=recipients.filter(p=>p.id!=='me'&&[p.name,p.handle].join(' ').toLowerCase().includes(q)).map(p=>`<button class="dm-recipient" data-message-recipient="${esc(p.key)}">${avatar(p)}<span><b>${esc(p.name)}</b><small>@${esc(p.handle)}</small></span><em>${p.demo?'Perfil fictício':'Admin da prévia'}</em></button>`).join('')||'<div class="dm-empty">Nenhum participante encontrado.</div>';
  }
  async function picker(){
    drafts.set(selected,input.value);selected=null;restart();$('message-chat').hidden=true;$('message-picker').hidden=false;
    try{recipients=(await request(urls.data)).people;drawRecipients();$('message-recipient-search').focus();}catch(e){toast(e.message);}
  }
  $('message-bell').onclick=open;$('message-new').onclick=picker;
  $('message-search').oninput=drawInbox;$('message-recipient-search').oninput=drawRecipients;
  input.oninput=()=>{drafts.set(selected,input.value);$('message-error').textContent='';};
  input.onkeydown=e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();$('message-form').requestSubmit();}};
  history.onscroll=markRead;
  $('message-form').onsubmit=async e=>{
    e.preventDefault();if(sending||!selected||visitor)return;const id=selected,text=input.value.trim();if(!text)return;
    let retry=retries.get(id);if(!retry||retry.text!==text){retry={text,request_key:crypto.randomUUID()};retries.set(id,retry);}sending=true;$('message-send').disabled=true;$('message-error').textContent='';
    try{const data=await request(urls.messageSend,{conversation:id,...retry});retries.delete(id);if(drafts.get(id)?.trim()===text){drafts.delete(id);if(selected===id)input.value='';}if(!visitor){accept(data);if(selected===id)drawChat(true);}}catch(err){$('message-error').textContent=err.message;}finally{sending=false;$('message-send').disabled=false;}
  };
  $('message-simulate').onclick=async()=>{
    if(!selected||visitor)return;const b=$('message-simulate');b.disabled=true;
    try{accept(await request(urls.messageDemo,{conversation:selected,request_key:crypto.randomUUID()}),true);}catch(e){toast(e.message);}finally{b.disabled=false;}
  };
  document.addEventListener('click',async e=>{
    const b=e.target.closest('button');if(!b||visitor)return;
    if(b.dataset.messageProfile){await open();await start(b.dataset.messageProfile);}
    else if(b.dataset.messageConversation)await choose(b.dataset.messageConversation);
    else if(b.dataset.messageRecipient)await start(b.dataset.messageRecipient);
    else if(b.hasAttribute('data-message-new'))await picker();
    else if(b.dataset.messageEmoji){const start=input.selectionStart,end=input.selectionEnd;input.setRangeText(b.dataset.messageEmoji,start,end,'end');drafts.set(selected,input.value);input.focus();}
    else if(b.hasAttribute('data-message-older')){const id=selected,chat=chats.get(id);if(!chat?.messages.length)return;b.disabled=true;try{const before=chat.messages[0].id;mergeChat(await request(endpoint(id)+'?before='+before),true);if(selected===id)drawChat(false,true);}catch(err){toast(err.message);}finally{b.disabled=false;}}
  });
  dialog.addEventListener('close',()=>{drafts.set(selected,input.value);selected=null;if(!visitor)restart();});
  window.addEventListener('feed-preview-mode',e=>{visitor=e.detail.visitor;$('message-bell').hidden=visitor;if(visitor){stop();dialog.close();}else initialize();});
  window.addEventListener('pagehide',stop);window.addEventListener('pageshow',e=>{if(e.persisted&&!visitor)initialize();});
  document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')markRead();});
  async function initialize(){try{const data=await request(urls.messages);if(visitor)return;accept(data);}catch{status('Reconectando mensagens…');if(!visitor)fallback();}connect();}
  initialize();
})();
