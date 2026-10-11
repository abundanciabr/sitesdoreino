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
    const inner=card.querySelector('.expanded-inner');
    inner.replaceChildren(beltPanel(index));
    const enlarge=document.createElement('button');enlarge.type='button';enlarge.className='detail-button checklist-back';enlarge.textContent='Ampliar meu progresso';
    enlarge.addEventListener('click',()=>openDetails(index));inner.append(enlarge);
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
  document.querySelector('#dialog-panel').replaceChildren(beltPanel(index,true));
  document.querySelector('#checklist-updated').textContent=consultedAtLabel(progress.consultado_em);
}
function beltPanel(index,modal=false){
  return createProgressPanel(journeyChecklist(progress,index,payload.atividades),{
    name:belts[index].name,number:number(index),white:index===0,modal,
    next:(index===0||index===current)&&belts[index+1]?belts[index+1].name:null,
    summary:progress.etapas[index].conquista
  });
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
      ||typeof item.detalhe!=='string'||!['concluido','andamento','pendente'].includes(item.estado)
      ||(item.bloqueado!==undefined&&typeof item.bloqueado!=='boolean'))throw new Error('Checklist incompleto');
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
  // A apresentação também fecha os passos posteriores se uma resposta antiga
  // ainda não trouxer os bloqueios. O servidor continua sendo a autoridade.
  let previousDone=true;
  const ordered=index===0?uniqueItems.map(item=>{
    const blocked=item.bloqueado===true||!previousDone;
    const state=blocked?'pendente':item.estado;
    previousDone=previousDone&&!blocked&&state==='concluido';
    return {...item,bloqueado:blocked,estado:state};
  }):uniqueItems;
  return {disponivel:true,itens:ordered,observacao:[...notes].join(' ')};
}

function whiteBeltActions(progress){
  return createProgressPanel(journeyChecklist(progress,0),{name:'Branca',number:'01',next:'Amarela',white:true});
}

function createProgressPanel(details,options){
  const node=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  const icon=name=>`<svg aria-hidden="true"><use href="#${name}"/></svg>`;
  const panel=node('section','progress-panel');panel.setAttribute('aria-label',`Progresso da faixa ${options.name}`);
  const header=node('div','progress-heading');
  const copy=node('div','progress-heading-copy');
  const title=node(options.modal?'h2':'h3','progress-title','Um passo de cada vez.');if(options.modal)title.id='dialog-title';
  const summary=node('p','progress-summary',options.next?'Próximo marco: ':options.summary);
  if(options.next)summary.append(node('strong','',`Faixa ${options.next}`));
  copy.append(node('span','dialog-eyebrow',`FAIXA ${options.name.toLocaleUpperCase('pt-BR')} · SEU PROGRESSO`),title,summary);
  const badge=node('div','progress-badge');badge.setAttribute('aria-hidden','true');badge.append(node('span','',options.number));
  header.append(copy,badge);panel.append(header);
  const available=details.disponivel&&(!options.white||details.itens.length===4);
  if(!available){panel.append(node('p','checklist-observation','Não foi possível consultar suas etapas agora. Atualize em instantes.'));return panel;}
  const total=details.itens.length,done=details.itens.filter(item=>item.estado==='concluido'&&!item.bloqueado).length;
  const percent=total?Math.round(done*100/total):0;
  const completion=node('div','checklist-completion');
  const numbers=node('div','checklist-numbers');const fraction=node('span','checklist-fraction');
  fraction.append(node('strong','',`${done} de ${total}`),node('span','',` ${total===1?'etapa concluída':'etapas concluídas'}`));
  numbers.append(fraction,node('span','checklist-percent',`${percent}%`));
  const meter=node('div','checklist-meter');meter.setAttribute('role','progressbar');meter.setAttribute('aria-label','Etapas concluídas');meter.setAttribute('aria-valuemin','0');meter.setAttribute('aria-valuemax','100');meter.setAttribute('aria-valuenow',String(percent));
  const fill=node('span','');fill.style.width=`${percent}%`;meter.append(fill);completion.append(numbers,meter);panel.append(completion);
  const list=node('ol','checklist-path');
  const focus=details.itens.find(item=>!item.bloqueado&&item.estado==='andamento')||details.itens.find(item=>!item.bloqueado&&item.estado==='pendente');
  details.itens.forEach((item,index)=>{
    const blocked=item.bloqueado===true;
    const state=blocked?'pendente':item.estado;
    const current=item===focus;
    const row=node('li',`checklist-step ${state}${current?' is-focus':''}${blocked?' is-locked':''}`);row.dataset.estado=state;row.dataset.bloqueado=String(blocked);
    if(blocked)row.setAttribute('aria-disabled','true');
    const mark=node('span','checklist-node');mark.setAttribute('aria-hidden','true');if(state==='concluido')mark.innerHTML=icon('check');
    const content=node('div','checklist-copy');
    const heading=node(options.modal?'h3':'h4','',`${options.white?`${index+1}. `:''}${item.titulo}`);
    const detail=blocked&&options.white?`Disponível após concluir e receber os XP de “${details.itens[index-1]?.titulo||'Meu motivo'}”.`:item.detalhe;
    content.append(heading,node('p','',detail));
    if(item.acao&&!blocked){
      const action=node('a',state==='concluido'?'checklist-review':'primary checklist-action',state==='concluido'?'Revisar':item.acao.rotulo);
      action.href=item.acao.url;
      if (item.acao.url === '/conquistas/inicio/motivo/') {
        if (state !== 'concluido') action.textContent = 'Definir meus motivos';
        action.addEventListener('click', event => {
          if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || event.button > 0) return;
          event.preventDefault(); openMotivo(action);
        });
      }
      if(state!=='concluido')action.insertAdjacentHTML('beforeend',icon('arrow'));
      content.append(action);
    }
    const status=node('span','checklist-status',state==='concluido'?'Concluído':current?(state==='andamento'?'Em andamento':'Disponível'):'Pendente');
    if(blocked)status.insertAdjacentHTML('afterbegin',icon('lock'));
    row.append(mark,content,status);list.append(row);
  });panel.append(list);
  const legend=node('div','checklist-legend');
  [['concluido','Já fez'],['andamento','Em andamento'],['pendente','Ainda precisa fazer']].forEach(([state,label])=>{
    const item=node('span',state);const mark=node('i','checklist-node');mark.setAttribute('aria-hidden','true');if(state==='concluido')mark.innerHTML=icon('check');item.append(mark,node('span','',label));legend.append(item);
  });panel.append(legend);
  const note=node('p','progress-note',options.white?'Conclua uma tarefa, receba seus XP e volte à faixa para o próximo passo. Suas respostas e seus arquivos continuam privados.':'Seu progresso acompanha os registros da jornada.');panel.append(note);
  if(details.observacao)panel.append(node('p','checklist-observation',details.observacao));
  return panel;
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

let motivoDialog, motivoContent, motivoScope, motivoController, motivoOpener, motivoLoad = 0;
const motivoScripts = new Map();
function loadMotivoScript(src) {
  if (!motivoScripts.has(src)) motivoScripts.set(src, new Promise((resolve, reject) => {
    const script = document.createElement('script'); script.src = src;
    script.onload = resolve;
    script.onerror = () => { motivoScripts.delete(src); script.remove(); reject(new Error('Não foi possível abrir agora. Tente novamente.')); };
    document.head.append(script);
  }));
  return motivoScripts.get(src);
}
async function loadMotivo(url) {
  const currentLoad = ++motivoLoad;
  motivoController?.destroy(); motivoController = null;
  const loading = document.createElement('p'); loading.textContent = 'Abrindo seus motivos…'; loading.setAttribute('role', 'status');
  motivoScope.replaceChildren(loading); motivoContent.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(url, {credentials: 'same-origin', cache: 'no-store'});
    if (!response.ok) throw new Error('Não foi possível abrir agora. Tente novamente.');
    const page = new DOMParser().parseFromString(await response.text(), 'text/html');
    const form = page.querySelector('#inicio-jornada'), receipt = page.querySelector('.celebracao');
    if (!form && !receipt) throw new Error('Sua sessão pode ter expirado. Entre novamente na sua conta para continuar.');
    await loadMotivoScript(form ? '/conquistas/static/inicio.js?v=10' : '/conquistas/static/inicio_conquista.js?v=3');
    if (currentLoad !== motivoLoad || !motivoDialog.open) return;
    const styles = Array.from(page.querySelectorAll('link[rel="stylesheet"]')).filter(link => new URL(link.getAttribute('href'), window.location.origin).pathname.startsWith('/conquistas/static/'));
    const base = document.createElement('style');
    base.textContent = ':host{display:block;color:#172b48;font:16px/1.6 system-ui,sans-serif} .motivo-recibo{--papel:#f8faf5;--escuro:#253923;--cinza:#667363;--verde:#58ae17;color:var(--escuro);background:var(--papel);min-height:100%;padding:16px 0;font-family:Nunito,system-ui,sans-serif} .motivo-recibo .celebracao{margin-top:0}@media(prefers-color-scheme:dark){.motivo-recibo{--papel:#151e19;--escuro:#f2f7ec;--cinza:#afbaaa}}';
    const wrapper = document.createElement('div'); wrapper.className = form ? 'inicio-embutido' : 'motivo-recibo ' + page.body.className;
    wrapper.append(form || receipt);
    motivoScope.replaceChildren(base, ...styles, wrapper);
    const host = {close: () => motivoDialog.close(), navigate: loadMotivo};
    if (form) motivoController = window.iniciarJornada(motivoScope, host);
    else window.iniciarConquista(motivoScope, host);
    motivoContent.scrollTop = 0;
  } catch (error) {
    if (currentLoad !== motivoLoad || !motivoDialog.open) return;
    const message = document.createElement('p'); message.textContent = error.message; message.setAttribute('role', 'alert');
    const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Tentar novamente'; retry.addEventListener('click', () => loadMotivo(url));
    motivoScope.replaceChildren(message, retry);
  } finally { if (currentLoad === motivoLoad) motivoContent.removeAttribute('aria-busy'); }
}
function openMotivo(opener) {
  if (!motivoDialog) {
    motivoDialog = document.createElement('dialog'); motivoDialog.className = 'motivo-dialog';
    motivoDialog.setAttribute('aria-label', 'Definir meus motivos');
    const close = document.createElement('button'); close.type = 'button'; close.className = 'motivo-close';
    close.textContent = '×'; close.setAttribute('aria-label', 'Fechar meus motivos');
    motivoContent = document.createElement('div'); motivoContent.className = 'motivo-content';
    motivoScope = motivoContent.attachShadow({mode: 'open'});
    const requestClose = () => motivoController ? motivoController.close() : motivoDialog.close();
    close.addEventListener('click', requestClose);
    motivoDialog.addEventListener('cancel', event => { event.preventDefault(); requestClose(); });
    motivoDialog.addEventListener('close', () => {
      motivoLoad++; motivoController?.destroy(); motivoController = null; motivoScope.replaceChildren();
      const inDetails = document.querySelector('#detail-dialog').open;
      refreshJourney().then(() => {
        const panel = document.querySelector(inDetails ? '#dialog-panel' : '#panel-1');
        (panel?.querySelector('a[href="/conquistas/inicio/motivo/"]') || motivoOpener)?.focus({preventScroll: true});
      });
    });
    motivoDialog.append(close, motivoContent); document.body.append(motivoDialog);
  }
  motivoOpener = opener;
  motivoDialog.showModal();
  loadMotivo('/conquistas/inicio/motivo/?embutido=1');
}
