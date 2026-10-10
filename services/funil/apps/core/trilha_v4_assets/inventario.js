'use strict';
const context=JSON.parse(document.querySelector('#trilha-data').textContent);
const endpoint='/conquistas/inventario/';
let data=null, busy=false, selectedOrder=null, previousCurrent=null;
const q=s=>document.querySelector(s);
function el(tag,text){const node=document.createElement(tag);node.textContent=text;return node;}
function message(text,error=false){q('#notice').textContent=text;q('#notice').classList.toggle('error',error);}
function validate(value){
  if(value.pessoa_id!==context.pessoa_id||value.site_id!==context.site_id){q('#inventory-content').hidden=true;throw new Error('Sua sessão mudou. Reabra o inventário antes de continuar.');}
  if(!Array.isArray(value.etapas)||value.etapas.length!==13||!Array.isArray(value.anexos)||typeof value.csrf!=='string')throw new Error('Não foi possível consultar seus registros. Recarregue a página.');
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
    if(!new RegExp('^/conquistas/inventario/arquivos/[0-9]+/$').test(a.url))return;
    const link=el('a',a.nome);link.href=a.url;item.append(link,el('small',`${a.tamanho<1024?a.tamanho+' bytes':a.tamanho<1048576?Math.ceil(a.tamanho/1024)+' KB':(a.tamanho/1048576).toLocaleString('pt-BR',{maximumFractionDigits:2})+' MB'} · arquivo privado`));target.append(item);
  });
}
function render(){
  q('#inventory-content').hidden=false;
  if(selectedOrder===null)selectedOrder=location.hash==='#primeiro-item'&&data.etapas[1].alcancada?2:data.atual_ordem;
  else if(selectedOrder===previousCurrent||!data.etapas.some(e=>e.ordem===selectedOrder&&e.alcancada))selectedOrder=data.atual_ordem;
  previousCurrent=data.atual_ordem;
  const shownSteps=inventoryStepsFor(data,selectedOrder);
  // Fora do cartão selecionado, nenhum formulário fica visível ou focável.
  const parts=q('#inventory-parts');
  ['primeiro-item','minhas-entregas','minha-meta','recebimentos','minha-historia'].forEach(id=>parts.append(q('#'+id)));

  const first=data.etapas.find(e=>e.ordem===2), hasFile=data.anexos.some(a=>a.passo===2);
  q('.save-file').hidden=first.alcancada;
  q('#first-state').textContent=first.alcancada?'CONCLUÍDO':hasFile?'ARQUIVO GUARDADO':'PENDENTE';
  q('#first-file').required=first.alcancada||!hasFile;
  q('#first-form [name=acao]').value=first.alcancada?'anexo':'declaracao';
  q('#first-submit').textContent=first.alcancada?'Guardar outro arquivo →':'Concluí meu item 3D →';
  q('#first-declaration').textContent=first.alcancada?'Sua conclusão já está registrada. Os arquivos ficam guardados aqui.':'“Concluí meu primeiro item 3D e consigo mostrar o resultado.”';
  fileList(q('#first-files'),2);
  q('#current-belt').textContent=`Faixa atual: ${data.etapas.find(e=>e.ordem===data.atual_ordem).nome}`;

  q('#goal').value=data.meta_cents===null?'':(data.meta_cents/100).toFixed(2);q('#purpose').value=data.proposito;
  q('#received-total').textContent=`${data.total} em recebimentos reconhecidos pelo conteúdo dos prints.`;
  q('#receipts').replaceChildren();data.recebimentos.forEach(r=>q('#receipts').append(el('li',`${r.valor} · ${r.estado} · ${r.data}`)));
  q('#history').replaceChildren();data.historico.forEach(r=>{const li=el('li',r.texto);li.append(el('time',new Date(r.criado_em).toLocaleString('pt-BR')));q('#history').append(li);});
  if(!data.historico.length)q('#history').append(el('li','Seus registros aparecerão aqui conforme você avançar.'));
  q('#deliveries').replaceChildren();
  [3,4].filter(ordem=>shownSteps.includes(ordem)).forEach(ordem=>{const etapa=data.etapas.find(e=>e.ordem===ordem), details=document.createElement('details');details.append(el('summary',`${ordem===3?'Minha prática no Sandbox':'Meu trabalho real na Fila'} · ${etapa.alcancada?'Concluído':'Pendente'}`));
    details.append(el('p',etapa.conquista));const link=el('a',ordem===3?'Abrir Sandbox →':'Abrir Fila →');link.href=ordem===3?'/encomendas/sandbox/':'/encomendas/fila/';link.className='text-link';details.append(link);
    const files=el('ul','');files.className='files';fileList(files,ordem);details.append(files);
    const form=document.createElement('form');
    for(const [name,value] of Object.entries({acao:etapa.alcancada?'anexo':'declaracao',passo:String(ordem),estado:'feito'})){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.append(input);}
    const label=el('label',etapa.alcancada?'Guardar um arquivo desta entrega':'Arquivo da entrega (opcional)');label.htmlFor=`file-${ordem}`;const input=document.createElement('input');input.type='file';input.name='arquivo';input.id=label.htmlFor;input.accept=q('#first-file').accept;input.required=etapa.alcancada;form.append(label,input);
    const button=el('button',etapa.alcancada?'Guardar arquivo':'Concluí e entreguei este trabalho');button.className='primary';button.type='submit';form.append(button);form.addEventListener('submit',submit);details.append(form);details.open=true;q('#deliveries').append(details);
  });
  renderBelts(shownSteps);
}

function inventoryStepsFor(value,selected){
  const own=value.etapas.find(e=>e.ordem===selected);
  if(!own?.alcancada)return [];
  return selected===value.atual_ordem&&selected<13?[selected,selected+1]:[selected];
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
      if(shownSteps.includes(2))body.append(q('#primeiro-item'));
      if(shownSteps.some(n=>n===3||n===4))body.append(q('#minhas-entregas'));
      if(shownSteps.some(n=>n>=6)&&step.ordem<13)body.append(q('#minha-meta'));
      if(shownSteps.some(n=>n>=5)&&step.ordem<13)body.append(q('#recebimentos'));
      if(step.ordem>=5&&next&&step.ordem===data.atual_ordem){const target=el('p',next.conquista);target.className='belt-result';body.append(target);}
      if(step.ordem===13){const finish=el('p','Sua jornada está registrada. Veja abaixo o caminho que você construiu.');finish.className='belt-result';body.append(finish);}
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

async function submit(event){
  event.preventDefault();if(busy||!data)return;
  const form=event.currentTarget; if(!form.reportValidity())return;
  const body=new FormData(form);if(event.submitter?.name==='acao')body.set('acao',event.submitter.value);body.set('revisao',String(data.revisao));body.set('chave',data.chave);body.set('contexto_pessoa',context.pessoa_id);body.set('contexto_site',context.site_id);
  const acao=body.get('acao');busy=true;document.querySelectorAll('button[type=submit]').forEach(b=>b.disabled=true);message('Guardando seu registro…');
  try{data=await request({method:'POST',headers:{'X-CSRFToken':data.csrf},body});form.reset();render();message(acao==='recebimento'?'Recebimento enviado para leitura. O resultado aparecerá nos seus registros.':acao==='declaracao'?'Conclusão registrada. Sua trilha já acompanha essa conquista.':'Registro guardado no seu inventário.');}
  catch(error){message(error.message,true);q('#notice').scrollIntoView({block:'center',behavior:'smooth'});}
  finally{busy=false;document.querySelectorAll('button[type=submit]').forEach(b=>b.disabled=false);}
}
document.querySelectorAll('form').forEach(form=>form.addEventListener('submit',submit));
request().then(value=>{data=value;render();message('Seus registros são privados e pertencem à sua conta.');if(location.hash==='#primeiro-item')q('#primeiro-item').scrollIntoView({block:'start'});}).catch(error=>message(error.message,true));
