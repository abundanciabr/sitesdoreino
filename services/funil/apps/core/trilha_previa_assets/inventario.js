'use strict';
const previa='/trilha/previa/';
const context=JSON.parse(document.querySelector('#trilha-data').textContent);
const endpoint=previa+'inventario/api/';
let data=null, busy=false, selectedOrder=null, previousCurrent=null;
const q=s=>document.querySelector(s);
function el(tag,text){const node=document.createElement(tag);node.textContent=text;return node;}
function message(text,error=false){q('#notice').textContent=text;q('#notice').classList.toggle('error',error);}
function validate(value){
  if(value.pessoa_id!==context.pessoa_id||value.site_id!==context.site_id){q('#inventory-content').hidden=true;throw new Error('Sua sessão mudou. Reabra o inventário antes de continuar.');}
  if(!Array.isArray(value.etapas)||![7,13].includes(value.etapas.length)||!Array.isArray(value.anexos)||typeof value.csrf!=='string')throw new Error('Não foi possível consultar seus registros. Recarregue a página.');
  value.graus_historicos=Array.isArray(value.graus_historicos)?value.graus_historicos.filter(g=>g&&Number.isInteger(g.ordem)&&g.ordem>=7&&g.ordem<=13&&Number.isInteger(g.bonus_xp)&&g.bonus_xp>=0&&typeof g.conquistada_em==='string'&&!Number.isNaN(Date.parse(g.conquistada_em))):[];
  return value;
}
async function request(options={}){
  const response=await fetch(endpoint,{credentials:'same-origin',cache:'no-store',...options});
  let value;try{value=await response.json();}catch{throw new Error('Não foi possível concluir agora. Atualize a página e confira seus registros antes de tentar novamente.');}
  if(!response.ok){if(response.status===403)q('#inventory-content').hidden=true;if(response.status===400&&value.detail?.includes('outra aba')){data=await request();render();}throw new Error(value.detail||'Não foi possível concluir agora. Confira seus registros antes de tentar novamente.');}
  return validate(value);
}
function fileList(target,passo){
  target.replaceChildren();
  data.anexos.filter(a=>a.passo===passo).forEach(a=>{const item=el('li','');
    if(!new RegExp('^'+previa+'inventario/arquivos/[0-9]+/$').test(a.url))return;
    const link=el('a',a.nome);link.href=a.url;item.append(link,el('small',`${a.tamanho<1024?a.tamanho+' bytes':a.tamanho<1048576?Math.ceil(a.tamanho/1024)+' KB':(a.tamanho/1048576).toLocaleString('pt-BR',{maximumFractionDigits:2})+' MB'} · arquivo privado`));target.append(item);
  });
}
function render(){
  q('#inventory-content').hidden=false;
  if(selectedOrder===null)selectedOrder=location.hash==='#primeiro-item'&&data.etapas[2].alcancada?3:data.atual_ordem;
  else if(selectedOrder===previousCurrent||!data.etapas.some(e=>e.ordem===selectedOrder&&e.alcancada))selectedOrder=data.atual_ordem;
  previousCurrent=data.atual_ordem;
  const shownSteps=inventoryStepsFor(data,selectedOrder);
  // Fora do cartão selecionado, nenhum formulário fica visível ou focável.
  const parts=q('#inventory-parts');
  ['branca-requisitos','primeiro-item','apresentar-item','minhas-entregas','minha-meta','recebimentos','minha-historia'].forEach(id=>parts.append(q('#'+id)));

  const itemStage=data.etapas.find(e=>e.ordem===3), fileStage=data.etapas.find(e=>e.ordem===4);
  const start=data.inicio||{};
  const requirements=inventoryStartSteps(start);
  requirements.slice(0,2).forEach(step=>{const node=q('#branca-'+step.id),link=node.parentElement;
    node.textContent=step.done?'Concluído · pode revisar':step.blocked?'🔒 Pendente':'Disponível';
    link.dataset.estado=step.done?'concluido':'pendente';link.setAttribute('aria-disabled',String(step.blocked));
    if(step.blocked)link.removeAttribute('href');else link.href=step.url;
  });
  q('#branca-resumo').textContent=`${requirements.slice(0,2).filter(step=>step.done).length} de 2 passos concluídos. A faixa chega após a avaliação do seu compromisso.`;
  const itemRequirement=requirements[2], fileRequirement=requirements[3];
  const firstLink=q('#first-link');firstLink.setAttribute('aria-disabled',String(itemRequirement.blocked));
  if(itemRequirement.blocked)firstLink.removeAttribute('href');else firstLink.href=itemRequirement.url;
  q('#first-state').textContent=itemStage.alcancada?'CONCLUÍDO':itemRequirement.done?'PODE REVISAR':itemRequirement.blocked?'BLOQUEADO':'PENDENTE';
  q('#first-item-summary').textContent=start.item_nome?`${start.item_nome}${start.item_acao?' · '+start.item_acao:''}`:'O relato do nome e da ação concreta é feito na etapa da faixa azul.';
  const redLink=q('#red-link');redLink.setAttribute('aria-disabled',String(fileRequirement.blocked));
  if(fileRequirement.blocked)redLink.removeAttribute('href');else redLink.href=fileRequirement.url;
  q('#red-state').textContent=fileStage.alcancada?'CONCLUÍDO':fileRequirement.done?'PODE REVISAR':fileRequirement.blocked?'AGUARDA A FAIXA AZUL':'PENDENTE';
  fileList(q('#first-files'),2);
  q('#current-belt').textContent=`Faixa atual: ${data.etapas.find(e=>e.ordem===data.atual_ordem).nome}`;

  q('#goal').value=data.meta_cents===null?'':(data.meta_cents/100).toFixed(2);q('#purpose').value=data.proposito;
  q('#received-total').textContent=`${data.total} em recebimentos reconhecidos pelo conteúdo dos prints.`;
  q('#receipts').replaceChildren();data.recebimentos.forEach(r=>q('#receipts').append(el('li',`${r.valor} · ${r.estado} · ${r.data}`)));
  q('#history').replaceChildren();data.historico.forEach(r=>{const li=el('li',r.texto);li.append(el('time',new Date(r.criado_em).toLocaleString('pt-BR')));q('#history').append(li);});
  if(!data.historico.length)q('#history').append(el('li','Seus registros aparecerão aqui conforme você avançar.'));
  const roman=['I','II','III','IV','V','VI','VII'];
  const preserved=data.etapas.length===7&&['ugc','jogo','aprender'].includes(data.caminho)?data.graus_historicos:[];
  if(preserved.length){const note=el('li','');const detail=el('small',`Graus anteriores preservados: ${preserved.map(g=>`Grau ${roman[g.ordem-7]} · +${g.bonus_xp.toLocaleString('pt-BR')} XP · ${new Date(g.conquistada_em).toLocaleDateString('pt-BR')}`).join(' | ')}`);detail.className='fine';note.append(detail);q('#history').append(note);}
  // A faixa atual não esconde os arquivos que a pessoa já guardou.
  data.anexos.forEach(a=>{if(!new RegExp('^'+previa+'inventario/arquivos/[0-9]+/$').test(a.url))return;const li=el('li','');const link=el('a',a.nome);link.href=a.url;li.append(link,el('small','Arquivo privado preservado'));q('#history').append(li);});
  q('#deliveries').replaceChildren();
  if(data.caminho==='freelancer'){
    [5,6].filter(ordem=>shownSteps.includes(ordem)).forEach(ordem=>{const etapa=data.etapas.find(e=>e.ordem===ordem);if(!etapa)return;const details=document.createElement('details');details.append(el('summary',`${ordem===5?'Minha prática no Sandbox':'Meu trabalho real na Fila'} · ${etapa.alcancada?'Concluído':'Pendente'}`));
      details.append(el('p',etapa.conquista));const link=el('a',ordem===5?'Abrir Sandbox →':'Abrir Fila →');link.href=ordem===5?previa+'sandbox/':previa+'fila/';link.className='text-link';details.append(link);
      const files=el('ul','');files.className='files';fileList(files,ordem);details.append(files);
      details.append(el('p','A conclusão depende da avaliação do Sandbox ou do aceite real da entrega na Fila.'));details.open=true;q('#deliveries').append(details);
    });
  }else if(['ugc','jogo','aprender'].includes(data.caminho)){
    const activity=data.etapas.find(etapa=>etapa.ordem>=5&&!etapa.alcancada&&shownSteps.includes(etapa.ordem));
    if(activity){const details=document.createElement('details');details.append(el('summary',`Prática da faixa ${activity.nome} · Disponível`));details.append(el('p',activity.conquista));const link=el('a','Abrir a prática e enviar para avaliação →');link.href=previa+'ciclo/';link.className='text-link';details.append(link);details.open=true;q('#deliveries').append(details);}
  }
  renderBelts(shownSteps);
}

function inventoryStepsFor(value,selected){
  const own=value.etapas.find(e=>e.ordem===selected);
  if(!own?.alcancada)return [];
  return selected===value.atual_ordem&&selected<value.etapas.length?[selected,selected+1]:[selected];
}
function inventoryStartSteps(start){
  let previousDone=true;
  return ['motivo','plano','item','envio'].map((id,index)=>{
    const saved=Array.isArray(start.etapas)?start.etapas.find(step=>step.etapa===index+1):null;
    const blocked=!previousDone||!saved||saved.bloqueada!==false||saved.liberada!==true;
    const done=!blocked&&saved?.concluida===true;
    previousDone=done;
    return {id,blocked,done,url:`${previa}inicio/${id==='plano'?'objetivo':id}/`};
  });
}
function renderBelts(shownSteps){
  const colors=['#e2e2e7','#e9c34b','#6299de','#dc6263','#65af88','#ae8b73'];
  const timeline=q('#inventory-timeline'),dock=q('#inventory-dock');timeline.replaceChildren();dock.replaceChildren();
  const icon=name=>`<svg aria-hidden="true" class="${name==='lock'?'lock-icon':''}"><use href="#${name}"/></svg>`;
  data.etapas.forEach(step=>{
    const locked=!step.alcancada, selected=step.ordem===selectedOrder;
    const number=String(step.ordem).padStart(2,'0');
    const row=el('li','');row.id=`inventario-faixa-${step.ordem}`;row.className=`stage ${locked?'locked':step.ordem!==data.atual_ordem?'done':''}${selected?' selected':''}`;
    row.style.setProperty('--belt',colors[step.ordem-1]||'#49494f');
    const mark=el('span',number);mark.className='track-mark';mark.setAttribute('aria-hidden','true');if(!locked&&step.ordem!==data.atual_ordem)mark.innerHTML=icon('check');row.append(mark);
    const card=el('div','');card.className='stage-card';
    const trigger=el('button','');trigger.type='button';trigger.className='stage-trigger';trigger.disabled=locked;trigger.id=`inventory-trigger-${step.ordem}`;trigger.setAttribute('aria-expanded',String(selected));trigger.setAttribute('aria-controls',`inventory-panel-${step.ordem}`);
    const swatch=el('span',number);swatch.className='swatch';swatch.setAttribute('aria-hidden','true');
    const title=el('span','');title.className='stage-text';const name=el('span',`Faixa ${step.nome}`);name.className='stage-name';title.append(name);
    const status=el('span',locked?'Bloqueada':step.ordem===data.atual_ordem?'Faixa atual':'Concluída');status.className='stage-status';trigger.append(swatch,title,status);trigger.insertAdjacentHTML('beforeend',icon(locked?'lock':'chevron'));
    trigger.addEventListener('click',()=>selectBelt(step.ordem));card.append(trigger);
    const panel=el('div','');panel.id=`inventory-panel-${step.ordem}`;panel.className='expanded';panel.inert=!selected;panel.setAttribute('role','region');panel.setAttribute('aria-labelledby',trigger.id);
    if(selected&&!locked){
      const inner=el('div','');inner.className='expanded-inner';const body=el('div','');body.className='inventory-panel';
      const label=el('p',step.ordem===data.atual_ordem?'SUA FAIXA ATUAL':'PARTE DA SUA HISTÓRIA');label.className='selected-label';body.append(label);
      const summary=el('p',step.conquista);summary.className='belt-result';body.append(summary);
      const next=data.etapas.find(e=>e.ordem===step.ordem+1);
      if(step.ordem===data.atual_ordem&&next){const hint=el('p',`Próximo marco: Faixa ${next.nome}`);hint.className='next-milestone';body.append(hint);}
      if(step.ordem===1)body.append(q('#branca-requisitos'));
      if(shownSteps.includes(3))body.append(q('#primeiro-item'));
      if(shownSteps.includes(4))body.append(q('#apresentar-item'));
      if(shownSteps.some(n=>n===5||n===6)&&q('#deliveries').children.length)body.append(q('#minhas-entregas'));
      if(data.etapas.length===13&&shownSteps.some(n=>n>=6)&&step.ordem<13)body.append(q('#minha-meta'));
      if(data.etapas.length===13&&shownSteps.some(n=>n>=5)&&step.ordem<13)body.append(q('#recebimentos'));
      if(step.ordem>=5&&next&&step.ordem===data.atual_ordem){const target=el('p',next.conquista);target.className='belt-result';body.append(target);}
      if(step.ordem===data.etapas.length){const finish=el('p','Sua jornada está registrada. Veja abaixo o caminho que você construiu.');finish.className='belt-result';body.append(finish);}
      const history=el('details','');history.className='belt-history';history.append(el('summary','Meu histórico registrado'),q('#minha-historia'));body.append(history);
      inner.append(body);panel.append(inner);
    }
    card.append(panel);row.append(card);timeline.append(row);
    const button=el('button','');button.type='button';button.className=`dock-button${locked?' locked':''}`;button.disabled=locked;button.setAttribute('aria-label',`${step.ordem}. Faixa ${step.nome}${locked?' — bloqueada':''}`);button.setAttribute('aria-current',String(selected));button.style.setProperty('--belt',colors[step.ordem-1]||'#49494f');
    button.innerHTML=locked?icon('lock'):'<span class="dock-dot" aria-hidden="true"></span>';
    const num=el('span',number);num.className='dock-number';const small=el('span',step.nome);small.className='dock-name';button.append(num,small);button.addEventListener('click',()=>selectBelt(step.ordem));dock.append(button);
  });
}
function selectBelt(order){
  if(busy||!data.etapas.some(e=>e.ordem===order&&e.alcancada))return;
  selectedOrder=order;previousCurrent=null;render();
  q(`#inventory-trigger-${order}`).focus({preventScroll:true});
  q(`#inventario-faixa-${order}`).scrollIntoView({block:'start',behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}

function safeConquistaUrl(value){
  try{
    const url=new URL(value,window.location.origin);
    const params=[...url.searchParams.entries()];
    if(url.origin!==window.location.origin||url.username||url.password||!/^\/trilha\/previa\/inicio\/conquista\/[0-9]+\/$/.test(url.pathname)||url.hash
      ||params.length>1||params.some(([key,token])=>key!=='comprovante'||!token))return null;
    return url.href;
  }catch{return null;}
}

async function submit(event){
  event.preventDefault();if(busy||!data)return;
  const form=event.currentTarget; if(!form.reportValidity())return;
  const body=new FormData(form);if(event.submitter?.name==='acao')body.set('acao',event.submitter.value);body.set('revisao',String(data.revisao));body.set('chave',data.chave);body.set('contexto_pessoa',context.pessoa_id);body.set('contexto_site',context.site_id);
  const acao=body.get('acao');busy=true;document.querySelectorAll('button[type=submit]').forEach(b=>b.disabled=true);message('Guardando seu registro…');
  try{data=await request({method:'POST',headers:{'X-CSRFToken':data.csrf},body});form.reset();render();if(data.conquista_url){const url=safeConquistaUrl(data.conquista_url);if(!url)throw new Error('A confirmação da avaliação está indisponível. Seus registros foram guardados.');window.location.assign(url);return;}message(acao==='recebimento'?'Recebimento enviado para leitura. O resultado aparecerá nos seus registros.':acao==='inicio-item'?'Item enviado para avaliação. O resultado aparecerá nos seus registros.':'Registro guardado no seu inventário.');}
  catch(error){message(error.message,true);q('#notice').scrollIntoView({block:'center',behavior:'smooth'});}
  finally{busy=false;document.querySelectorAll('button[type=submit]').forEach(b=>b.disabled=false);}
}
document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',submit));
request().then(value=>{data=value;render();message('Seus registros são privados e pertencem à sua conta.');if(location.hash==='#primeiro-item')q('#primeiro-item').scrollIntoView({block:'start'});}).catch(error=>message(error.message,true));
