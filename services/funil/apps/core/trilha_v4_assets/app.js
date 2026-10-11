'use strict';
function renderJourney(payload,view={}){
const icons = {arrow:'<svg aria-hidden="true"><use href="#arrow"/></svg>',check:'<svg aria-hidden="true"><use href="#check"/></svg>',chevron:'<svg aria-hidden="true"><use href="#chevron"/></svg>',lock:'<svg class="lock-icon" aria-hidden="true"><use href="#lock"/></svg>'};
const belts = [
  {name:'Branca',short:'Branca',category:'O começo de tudo',title:'Toda criação começa com curiosidade.',summary:'Conheça seu ambiente e dê o primeiro passo na modelagem 3D.',color:'#e2e2e7',wash:'#f6f6f8',tone:'#66666d',ink:'#73737a'},
  {name:'Amarela',short:'Amarela',category:'Seu primeiro modelo',title:'Uma ideia. Sua primeira forma.',summary:'Leve o que aprendeu para o Blender e crie seu primeiro item 3D.',color:'#e9c34b',wash:'#fdf9e9',tone:'#8c6b0b',ink:'#735d17'},
  {name:'Azul',short:'Azul',category:'Prática no Sandbox',title:'Experimente. Ajuste. Evolua.',summary:'Um espaço para testar seu modelo e descobrir o que pode ficar melhor.',color:'#6299de',wash:'#eef5fc',tone:'#2b65a6',ink:'#f9fcff'},
  {name:'Vermelha',short:'Vermelha',category:'Trabalho real',title:'Sua criação encontra o mundo.',summary:'Um projeto real. Um novo desafio. A hora de transformar prática em entrega.',color:'#dc6263',wash:'#fdf0ef',tone:'#b44348',ink:'#fff9f9'},
  {name:'Verde',short:'Verde',category:'Primeiro dinheiro',title:'O primeiro resultado tem outro valor.',summary:'Seu primeiro trabalho aprovado e o primeiro pagamento recebido.',color:'#65af88',wash:'#eef8f2',tone:'#317150',ink:'#f5fff9'},
  {name:'Marrom',short:'Marrom',category:'Consistência',title:'O seu melhor ganha continuidade.',summary:'Transforme a primeira experiência em uma prática que continua evoluindo.',color:'#ae8b73',wash:'#f8f3ef',tone:'#795b46',ink:'#fffbf7'},
  ...Array.from({length:7},(_,i)=>({name:`Preta ${i+1}º grau`,short:`${i+1}º grau`,category:i===6?'Mestre modelador':`Maestria · Grau ${String(i+1).padStart(2,'0')}`,title:i===6?'Sua evolução abre novos caminhos.':`Um novo grau. Mais possibilidades.`,summary:i===6?'Um portfólio de alto valor. Um horizonte de novas criações.':`O ${i+1}º grau da Faixa Preta é mais um capítulo da sua jornada na modelagem.`,color:'#49494f',wash:'#f2f2f5',tone:'#585860',ink:'#f6f6fa'}))
];
const progress = payload.progresso;
const current = progress.atual_ordem - 1;
const money = cents=>new Intl.NumberFormat('pt-BR',{style:'currency',currency:'BRL'}).format(cents/100);
const reached = index=>progress.etapas[index]?.alcancada===true;
const available = progress.etapas.flatMap((step,index)=>step.alcancada?[index]:[]);
belts.forEach((belt,index)=>{
  const step=progress.etapas[index];
  belt.summary=index>=5
    ?(progress.meta_escolhida?`Meta desta etapa: ${money(step.meta_cents)} em recebimentos confirmados.`:'Sua meta pessoal ainda não foi definida.')
    :step.conquista;
});
let selected = view.selected===view.current?current:reached(view.selected)?view.selected:current;
const timeline = document.querySelector('#timeline');
const dock = document.querySelector('#dock');
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
const dialog = document.querySelector('#detail-dialog');
const stages = [];
const dockButtons = [];
let openedIndex=view.detailIndex!=null&&view.detailIndex===view.current?current:view.detailIndex??null;
timeline.replaceChildren();dock.replaceChildren();
const number = index=>String(index+1).padStart(2,'0');
const state = index=>index===current?'Faixa atual':reached(index)?'Concluída':'Bloqueada';
const adjacent = direction=>available[available.indexOf(selected)+direction];

const doneCount=progress.etapas.filter(step=>step.alcancada).length;
document.querySelector('#completed-count').textContent=String(doneCount).padStart(2,'0');
document.querySelector('#remaining-count').textContent=String(13-doneCount).padStart(2,'0');
document.querySelector('.dial-number').textContent=number(current);
document.querySelector('#current-position').textContent=number(current);
document.querySelector('#current-belt').textContent=number(current);
const indicator=document.createElement('i');indicator.style.background=belts[current].color;
document.querySelector('.dial-name').replaceChildren(indicator,document.createTextNode(' '+belts[current].name.toLocaleUpperCase('pt-BR')));
document.querySelector('.object-footer>span').textContent=belts[current].category.toLocaleUpperCase('pt-BR');
document.querySelector('.hero-object').setAttribute('aria-label',`Faixa atual de ${payload.aluno.nome}: ${current+1} de 13, ${belts[current].name}.`);
const segments=progress.etapas.map((step,index)=>`${index===current?belts[index].color:step.alcancada?'#4884f6':'#d8e3f1'} ${index*360/13}deg ${(index+1)*360/13}deg`);
document.querySelector('.dial-track').style.background=`conic-gradient(from 0deg,${segments.join(',')})`;

belts.forEach((belt,index)=>{
  const locked=!reached(index);
  const dockButton = document.createElement('button');
  dockButton.className=`dock-button${locked?' locked':''}`;dockButton.type='button';dockButton.disabled=locked;
  dockButton.style.setProperty('--belt',belt.color);
  dockButton.setAttribute('aria-label',`${index+1}. Faixa ${belt.name}${locked?' — bloqueada':''}`);
  dockButton.title=`${index+1}. Faixa ${belt.name}${locked?' — disponível ao alcançar esta faixa':''}`;
  dockButton.innerHTML=`${locked?icons.lock:'<span class="dock-dot" aria-hidden="true"></span>'}<span class="dock-number" aria-hidden="true">${number(index)}</span><span class="dock-name" aria-hidden="true">${belt.short}</span>`;
  dockButton.addEventListener('click',()=>select(index,true));
  dock.append(dockButton);dockButtons.push(dockButton);
  const stage=document.createElement('li');stage.className=`stage ${locked?'locked':index!==current?'done':''}`;stage.id=`faixa-${index+1}`;
  stage.style.setProperty('--belt',belt.color);stage.style.setProperty('--wash',belt.wash);stage.style.setProperty('--tone',belt.tone);stage.style.setProperty('--swatch-ink',belt.ink);
  if(index===6){const chapter=document.createElement('p');chapter.className='chapter-label';chapter.textContent='FAIXA PRETA. SETE GRAUS DE EVOLUÇÃO.';stage.append(chapter);}
  const mark=document.createElement('span');mark.className='track-mark';mark.setAttribute('aria-hidden','true');mark.innerHTML=reached(index)&&index!==current?icons.check:number(index);if(index===6)mark.style.top='94px';
  stage.append(mark);
  const card=document.createElement('div');card.className='stage-card';
  card.innerHTML=`<button type="button" class="stage-trigger" ${locked?'disabled':''} aria-expanded="false" aria-controls="panel-${index+1}" id="trigger-${index+1}">
    <span class="swatch" aria-hidden="true">${number(index)}</span><span class="stage-text"><span class="stage-name">Faixa ${belt.name}</span><span class="stage-category">${belt.category}</span></span><span class="stage-status">${state(index)}</span>${locked?icons.lock:icons.chevron}
    </button><div class="expanded" id="panel-${index+1}" role="region" aria-labelledby="trigger-${index+1}" inert>${locked?'':`<div class="expanded-inner"><div class="focus-content"><div class="focus-copy"><span class="selected-label">${index===current?'SUA FAIXA ATUAL':'PARTE DA SUA HISTÓRIA'}</span><h3>${belt.title}</h3><p></p><button type="button" class="primary detail-button">${index===current?'Ver progresso':'Explorar esta faixa'} ${icons.arrow}</button></div><div class="medallion-scene" aria-hidden="true"><div class="medallion"><span>${number(index)}</span></div></div></div></div>`}</div>`;
  if(!locked){
    card.querySelector('.focus-copy p').textContent=belt.summary;
    if(index===0){
      card.querySelector('.detail-button').replaceWith(whiteBeltActions(progress));
    }else{
      card.querySelector('.detail-button').addEventListener('click',event=>openDetails(index,event.currentTarget));
    }
  }
  card.querySelector('.stage-trigger').addEventListener('click',()=>select(index,false));
  stage.append(card);timeline.append(stage);stages.push(stage);
});
function select(index,scroll){
  if(!reached(index))return;
  selected=index;
  stages.forEach((stage,i)=>{
    stage.classList.toggle('selected',i===selected);
    stage.querySelector('.stage-trigger').setAttribute('aria-expanded',String(i===selected));
    stage.querySelector('.expanded').inert=i!==selected;
    dockButtons[i].setAttribute('aria-current',String(i===selected));
  });
  document.querySelector('#position').textContent=number(selected);
  document.querySelector('#selected-label').textContent=`Faixa ${belts[selected].name}`;
  previous.disabled=adjacent(-1)===undefined;next.disabled=adjacent(1)===undefined;
  const box=dockButtons[selected].getBoundingClientRect();
  const frame=dock.parentElement.getBoundingClientRect();
  dock.parentElement.scrollTo({left:dock.parentElement.scrollLeft+box.left-frame.left-(frame.width-box.width)/2,behavior:'auto'});
  if(scroll) stages[selected].scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',block:'center'});
}
function showChecklist(index){
  const own=progress.etapas[index];
  const target=index===current?progress.etapas[index+1]:null;
  const details=journeyChecklist(progress,index,payload.atividades);
  document.querySelector('#dialog-eyebrow').textContent=`FAIXA ${belts[index].name.toLocaleUpperCase('pt-BR')} · SEU PROGRESSO`;
  document.querySelector('#dialog-title').textContent=target?'Seu próximo movimento.':'Sua conquista, registrada.';
  document.querySelector('#dialog-summary').textContent=target?`Próximo marco: Faixa ${belts[index+1].name}`:own.conquista;
  const tasks=document.querySelector('#task-list');tasks.replaceChildren();
  const counts={concluido:0,andamento:0,pendente:0};
  details.itens.forEach(item=>counts[item.estado]++);
  const focus=details.itens.find(item=>item.estado==='andamento')||details.itens.find(item=>item.estado==='pendente');
  details.itens.forEach(item=>{
    const task=document.createElement('li');task.className=`checklist-step ${item.estado}${item===focus?' is-focus':''}`;
    const mark=document.createElement('span');mark.className='checklist-node';mark.setAttribute('aria-hidden','true');
    if(item.estado==='concluido')mark.innerHTML=icons.check;
    const content=document.createElement('div');content.className='checklist-copy';
    const status=document.createElement('span');status.className='checklist-status';
    status.textContent={concluido:'CONCLUÍDO',andamento:'EM ANDAMENTO',pendente:item===focus?'PRÓXIMO PASSO · PENDENTE':'PENDENTE'}[item.estado];
    const heading=document.createElement('h3');heading.textContent=item.titulo;
    const evidence=document.createElement('p');evidence.textContent=item.detalhe;
    content.append(status,heading,evidence);
    if(item===focus){
      const art=document.createElement('div');art.className='checklist-art';art.setAttribute('aria-hidden','true');
      art.innerHTML='<svg viewBox="0 0 120 130"><path d="M60 8 110 35 110 93 60 122 10 93 10 35Z M10 35 60 65 110 35 M60 65V122 M35 22 85 51V108 M85 22 35 51V108 M10 64 60 94 110 64"/></svg>';
      content.append(art);
    }
    if(item.acao&&(item===focus||index===0)){
        const action=document.createElement('a');action.className='primary checklist-action';action.href=item.acao.url;
        action.append(document.createTextNode(item.acao.rotulo));action.insertAdjacentHTML('beforeend',icons.arrow);content.append(action);
    }
    task.append(mark,content);tasks.append(task);
  });
  document.querySelector('#checklist-done').textContent=details.disponivel?counts.concluido:'—';
  document.querySelector('#checklist-active').textContent=details.disponivel?counts.andamento:'—';
  document.querySelector('#checklist-pending').textContent=details.disponivel?counts.pendente:'—';
  document.querySelector('#checklist-done-label').textContent=counts.concluido===1?'concluída':'concluídas';
  document.querySelector('#checklist-pending-label').textContent=counts.pendente===1?'pendente':'pendentes';
  document.querySelector('#checklist-observation').textContent=details.observacao;
  const total=details.itens.length;
  const percent=total?Math.round(counts.concluido*100/total):0;
  document.querySelector('#checklist-completion').hidden=!details.disponivel||!total;
  document.querySelector('#checklist-fill').style.width=`${percent}%`;
  document.querySelector('.checklist-meter').setAttribute('aria-valuenow',String(percent));
  document.querySelector('#checklist-fraction').textContent=`${counts.concluido} de ${total} ${total===1?'etapa concluída':'etapas concluídas'}`;
  document.querySelector('#dialog-note').textContent=index===0?'Quatro requisitos para passar da faixa branca à amarela. Seus registros pessoais continuam privados.':'Atualizado pelos registros da sua jornada. As etapas exibidas não alteram os critérios das faixas.';
  document.querySelector('#checklist-updated').textContent=consultedAtLabel(progress.consultado_em);
}
function openDetails(index){
  if(!reached(index))return;
  openedIndex=index;showChecklist(index);
  if(!dialog.open)dialog.showModal();dialog.scrollTop=0;
  refreshJourney();
}
function closeDetails(){dialog.close();}
dialog.onclose=()=>{const index=openedIndex;openedIndex=null;stages[index]?.querySelector('.detail-button, .white-belt-action')?.focus({preventScroll:true});};
document.querySelector('.dialog-close').onclick=closeDetails;
document.querySelector('#back-to-journey').onclick=closeDetails;
document.querySelector('#checklist-refresh').onclick=()=>refreshJourney();
dialog.onclick=event=>{if(event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeDetails();};
document.querySelector('#resume').onclick=()=>select(current,true);
previous.onclick=()=>select(adjacent(-1),true);
next.onclick=()=>select(adjacent(1),true);
dock.onkeydown=event=>{
  const keys={ArrowRight:adjacent(1),ArrowLeft:adjacent(-1),Home:available[0],End:available[available.length-1]};
  if(Object.hasOwn(keys,event.key)){event.preventDefault();select(keys[event.key],true);dockButtons[selected].focus({preventScroll:true});}
};
select(selected,false);
if(dialog.open){
  if(reached(openedIndex))showChecklist(openedIndex);
  else{dialog.close();stages[current].querySelector('.detail-button, .white-belt-action')?.focus({preventScroll:true});}
}
document.querySelector('#resume').disabled=false;
document.querySelector('.hero-object').removeAttribute('aria-busy');
document.querySelector('.object-caption').textContent='SEU MOMENTO ATUAL';
return {snapshot:()=>({selected,current,detailIndex:dialog.open?openedIndex:null}),setConsultedAt(value){progress.consultado_em=value;document.querySelector('#checklist-updated').textContent=consultedAtLabel(value);}};
}

function consultedAtLabel(value){
  const when=new Date(value);
  return Number.isNaN(when.getTime())?'':`Consultado às ${new Intl.DateTimeFormat('pt-BR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}).format(when)}`;
}
function safeAction(action){
  if(action===null||action===undefined)return null;
  if(typeof action.rotulo!=='string'||!action.rotulo.trim()||typeof action.url!=='string'
    ||!/^\/(cursos|encomendas|forum|trilha|conquistas)(?:\/|$)/.test(action.url)
    ||/[\\\s]/.test(action.url)||action.url.includes('..'))throw new Error('Ação inválida');
  return {rotulo:action.rotulo,url:action.url};
}
function validateChecklist(checklist){
  if(checklist===undefined)return null;
  if(!checklist||!Array.isArray(checklist.itens)||!checklist.itens.length||checklist.itens.length>10
    ||typeof checklist.observacao!=='string')throw new Error('Checklist incompleto');
  const ids=new Set();
  const itens=checklist.itens.map(item=>{
    if(!item||typeof item.id!=='string'||!item.id||ids.has(item.id)||typeof item.titulo!=='string'
      ||typeof item.detalhe!=='string'||!['concluido','andamento','pendente'].includes(item.estado))throw new Error('Checklist incompleto');
    ids.add(item.id);return {...item,acao:safeAction(item.acao)};
  });
  return {...checklist,itens};
}
function validateActivities(data,context){
  if(!data||data.pessoa_id!==context.pessoa_id||data.site_id!==context.site_id
    ||!Array.isArray(data.atividades)||data.atividades.length>2)throw new Error('Atividade indisponível');
  const seen=new Set();
  return data.atividades.map(item=>{
    if(!item||![3,4].includes(item.ordem)||seen.has(item.ordem)
      ||!['andamento','pendente'].includes(item.estado)||typeof item.detalhe!=='string')throw new Error('Atividade indisponível');
    seen.add(item.ordem);return {...item,acao:safeAction(item.acao)};
  });
}
function journeyChecklist(progress,index,activities){
  const own=progress.etapas[index];
  const next=index===progress.atual_ordem-1?progress.etapas[index+1]:null;
  const sources=index===0?[progress.etapas[1]]:next?[own,next]:[own];
  if(sources.some(step=>!step.checklist))return {disponivel:false,itens:[],observacao:'O checklist está temporariamente indisponível. Tente atualizar em instantes.'};
  const notes=new Set();
  const itens=sources.flatMap(step=>{
    if(step.checklist.observacao)notes.add(step.checklist.observacao);
    const relevantItems=index>0&&step.ordem===2?step.checklist.itens.filter(item=>!['motivo-2','plano-2','envio-2'].includes(item.id)):step.checklist.itens;
    return relevantItems.map(item=>{
      if(step.alcancada||![3,4].includes(step.ordem)||item.id!==`criterio-${step.ordem}`)return item;
      if(!activities?.disponivel){notes.add('Não foi possível consultar os trabalhos agora. O estado abaixo considera somente os registros da jornada.');return item;}
      const activity=activities.itens.find(activity=>activity.ordem===step.ordem);
      return activity?{...item,estado:activity.estado,detalhe:activity.detalhe,acao:activity.acao}:item;
    });
  });
  let personalGoalShown=false;
  const uniqueItems=itens.filter(item=>{
    if(!/^meta-\d+$/.test(item.id))return true;
    if(personalGoalShown)return false;
    personalGoalShown=true;return true;
  });
  return {disponivel:true,itens:uniqueItems,observacao:[...notes].join(' ')};
}

function whiteBeltActions(progress){
  const details=journeyChecklist(progress,0);
  const group=document.createElement('div');group.className='white-belt-requirements';
  group.setAttribute('aria-label','Quatro requisitos da faixa branca');
  const heading=document.createElement('p');heading.className='white-belt-heading';
  heading.textContent='Quatro requisitos para chegar à faixa amarela';group.append(heading);
  if(!details.disponivel||details.itens.length!==4||details.itens.some(item=>!item.acao)){
    const notice=document.createElement('p');notice.textContent='Não foi possível abrir seus requisitos agora. Atualize a página em instantes.';group.append(notice);return group;
  }
  const list=document.createElement('ol');list.className='white-belt-actions';
  details.itens.forEach((item,index)=>{
    const row=document.createElement('li');
    const link=document.createElement('a');link.className='primary white-belt-action';link.href=item.acao.url;
    const title=document.createElement('span');title.textContent=`${index+1}. ${item.titulo}`;
    const state=document.createElement('small');state.className='white-belt-state';
    state.textContent={concluido:'Concluído · pode revisar',andamento:'Em andamento',pendente:'Para fazer'}[item.estado];
    link.dataset.estado=item.estado;link.append(title,state);row.append(link);list.append(row);
  });
  group.append(list);
  const count=document.createElement('p');count.className='white-belt-count';
  count.textContent=`${details.itens.filter(item=>item.estado==='concluido').length} de 4 requisitos concluídos. Você pode salvar e continuar depois.`;
  group.append(count);
  if(details.observacao){const note=document.createElement('p');note.className='white-belt-count';note.textContent=details.observacao;group.append(note);}
  return group;
}

function validateProgress(data, context){
  if(data&&(data.pessoa_id!==context.pessoa_id||data.site_id!==context.site_id)){const error=new Error('Sessão alterada');error.invalidIdentity=true;throw error;}
  const integer=value=>Number.isInteger(value)&&value>=0;
  if(!data||data.pessoa_id!==context.pessoa_id||data.site_id!==context.site_id
    ||!Array.isArray(data.etapas)||data.etapas.length!==13
    ||!integer(data.atual_ordem)||data.atual_ordem<1||data.atual_ordem>13
    ||!integer(data.total_cents)||typeof data.meta_escolhida!=='boolean'
    ||(data.meta_cents!==null&&!integer(data.meta_cents))
    ||(data.meta_escolhida&&!(data.meta_cents>0)))throw new Error('Progresso incompleto');
  const steps=[...data.etapas].sort((a,b)=>a.ordem-b.ordem);
  if(steps.some((step,index)=>!step||step.ordem!==index+1||typeof step.alcancada!=='boolean'
      ||typeof step.conquista!=='string'||(step.meta_cents!==null&&!integer(step.meta_cents))
      ||(index<5&&step.meta_cents!==null)
      ||(index>=5&&(data.meta_escolhida?step.meta_cents===null:step.meta_cents!==null))
      ||(step.alcancada_em!==null&&typeof step.alcancada_em!=='string'))
    ||steps.some(step=>step.alcancada!==(step.ordem<=data.atual_ordem)))
    throw new Error('Progresso incompleto');
  return {...data, etapas:steps.map(step=>({...step,checklist:validateChecklist(step.checklist)}))};
}

let journeyController;
let journeyFingerprint;
let pendingRefresh;
async function requestJson(url){
  const controller=new AbortController();
  const timer=setTimeout(()=>controller.abort(),15000);
  try{
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'},signal:controller.signal});
    if(response.status===403){const error=new Error('Sessão encerrada');error.status=403;throw error;}
    if(!response.ok)throw new Error('Consulta indisponível');
    return await response.json();
  }finally{clearTimeout(timer);}
}
async function refreshJourney(){
  if(pendingRefresh)return pendingRefresh;
  const context=JSON.parse(document.querySelector('#trilha-data').textContent);
  const refreshButton=document.querySelector('#checklist-refresh');
  refreshButton.disabled=true;
  if(document.querySelector('#detail-dialog').open)document.querySelector('#checklist-updated').textContent='Atualizando seus registros…';
  pendingRefresh=(async()=>{
    try{
      const [journeyResult,activityResult]=await Promise.allSettled([
        requestJson('/conquistas/minha-trilha/'),requestJson('/encomendas/minha-trilha/')
      ]);
      if(journeyResult.status==='rejected')throw journeyResult.reason;
      const progress=validateProgress(journeyResult.value,context);
      let activities={disponivel:false,itens:[]};
      if(activityResult.status==='fulfilled'){
        try{activities={disponivel:true,itens:validateActivities(activityResult.value,context)};}catch(error){/* Fonte indisponível não vira atividade presumida. */}
      }
      const fingerprint=JSON.stringify({progresso:{...progress,consultado_em:null},atividades:activities});
      if(journeyController&&journeyFingerprint===fingerprint){
        journeyController.setConsultedAt(progress.consultado_em);
      }else{
        const view=journeyController?.snapshot();
        const focusedAction=document.activeElement?.closest?.('.checklist-action')?.getAttribute('href');
        journeyController=renderJourney({...context,progresso:progress,atividades:activities},view);
        journeyFingerprint=fingerprint;
        if(focusedAction){const action=document.querySelector('.checklist-action');if(action?.getAttribute('href')===focusedAction)action.focus({preventScroll:true});}
      }
    }catch(error){
      if(error.status===403||error.invalidIdentity){
        if(document.querySelector('#detail-dialog').open)document.querySelector('#detail-dialog').close();
        document.querySelector('#timeline').replaceChildren();document.querySelector('#dock').replaceChildren();
        document.querySelector('#resume').disabled=true;journeyController=null;journeyFingerprint=null;
        if(error.invalidIdentity){document.querySelector('main').hidden=true;window.location.replace('/trilha/');return;}
        if(error.status===403){window.location.replace('/login?next=%2Ftrilha%2F');return;}
      }
      if(!journeyController){
        document.querySelector('.hero-object').removeAttribute('aria-busy');
        document.querySelector('.hero-object').setAttribute('aria-label','Progresso indisponível');
        document.querySelector('.object-caption').textContent='PROGRESSO INDISPONÍVEL';
        document.querySelector('.explore-hint').textContent='Não foi possível consultar seu progresso agora. Recarregue a página para tentar novamente.';
      }else{
        document.querySelector('#checklist-updated').textContent='Não foi possível atualizar. Os dados são da última consulta; tente novamente.';
      }
    }finally{refreshButton.disabled=false;pendingRefresh=null;}
  })();
  return pendingRefresh;
}
function loadJourney(){return refreshJourney();}
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refreshJourney();});
window.addEventListener('focus',()=>{if(!document.hidden)refreshJourney();});
setInterval(()=>{if(!document.hidden&&document.querySelector('#detail-dialog').open)refreshJourney();},30000);
loadJourney();
