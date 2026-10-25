'use strict';
function renderJourney(payload,view={}){
const icons = {arrow:'<svg aria-hidden="true"><use href="#arrow"/></svg>',check:'<svg aria-hidden="true"><use href="#check"/></svg>',chevron:'<svg aria-hidden="true"><use href="#chevron"/></svg>',lock:'<svg class="lock-icon" aria-hidden="true"><use href="#lock"/></svg>'};
const progress = payload.progresso;
const totalStages=progress.etapas.length;
const palette=[
  {color:'#e2e2e7',wash:'#f6f6f8',tone:'#66666d',ink:'#73737a'},
  {color:'#e9c34b',wash:'#fdf9e9',tone:'#8c6b0b',ink:'#735d17'},
  {color:'#6299de',wash:'#eef5fc',tone:'#2b65a6',ink:'#f9fcff'},
  {color:'#dc6263',wash:'#fdf0ef',tone:'#b44348',ink:'#fff9f9'},
  {color:'#65af88',wash:'#eef8f2',tone:'#317150',ink:'#f5fff9'},
  {color:'#ae8b73',wash:'#f8f3ef',tone:'#795b46',ink:'#fffbf7'},
  {color:'#49494f',wash:'#f2f2f5',tone:'#585860',ink:'#f6f6fa'}
];
const belts=progress.etapas.map((step,index)=>{
  const theme=palette[Math.min(index,palette.length-1)];
  const name=step.nome||step.conquista;
  const short=totalStages===7?name:name.replace(/^Preta\s*[·-]?\s*/i,'').replace(/\s*Grau/i,'');
  const goal=progress.etapas[index+1];
  const category=goal?`${goal.alcancada?'Trabalho já concluído':step.ordem===progress.atual_ordem?'Próximo trabalho':'Trabalho desta etapa'} · conquistar Faixa ${goal.nome||goal.conquista}: ${goal.conquista}`:(step.alcancada?'Percurso concluído. Todas as faixas deste caminho foram conquistadas.':'Último marco deste percurso.');
  return {name,short,category,title:name,summary:goal?.feedback||category,color:theme.color,wash:theme.wash,tone:theme.tone,ink:theme.ink};
});
const current = progress.atual_ordem - 1;
const reached = index=>progress.etapas[index]?.alcancada===true;
const available = progress.etapas.flatMap((step,index)=>step.alcancada?[index]:[]);
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
const state = index=>index===current?'Faixa atual':reached(index)?'Conquistada':'Bloqueada';
const adjacent = direction=>available[available.indexOf(selected)+direction];

const doneCount=progress.etapas.filter(step=>step.alcancada).length;
document.querySelector('#completed-count').textContent=String(doneCount).padStart(2,'0');
document.querySelector('#remaining-count').textContent=String(totalStages-doneCount).padStart(2,'0');
document.querySelectorAll('.stage-total').forEach(node=>node.textContent=String(totalStages));
document.querySelector('.dial-number').textContent=number(current);
document.querySelector('#current-position').textContent=number(current);
document.querySelector('#current-belt').textContent=number(current);
document.querySelectorAll('[data-dial-position]').forEach(node=>{
  const position=Number(node.dataset.dialPosition);
  node.textContent=number(Math.floor(totalStages*position/4));
});
const indicator=document.createElement('i');indicator.style.background=belts[current].color;
document.querySelector('.dial-name').replaceChildren(indicator,document.createTextNode(' '+belts[current].name.toLocaleUpperCase('pt-BR')));
document.querySelector('.object-footer>span').textContent=belts[current].category.toLocaleUpperCase('pt-BR');
document.querySelector('.hero-object').setAttribute('aria-label',`Faixa atual de ${payload.aluno.nome}: ${current+1} de ${totalStages}, ${belts[current].name}.`);
const segments=progress.etapas.map((step,index)=>`${index===current?belts[index].color:step.alcancada?'#4884f6':'#d8e3f1'} ${index*360/totalStages}deg ${(index+1)*360/totalStages}deg`);
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
  if(totalStages===13&&index===6){const chapter=document.createElement('p');chapter.className='chapter-label';chapter.textContent='FAIXA PRETA. SETE GRAUS DE EVOLUÇÃO.';stage.append(chapter);}
  const mark=document.createElement('span');mark.className='track-mark';mark.setAttribute('aria-hidden','true');mark.innerHTML=reached(index)&&index!==current?icons.check:number(index);if(totalStages===13&&index===6)mark.style.top='94px';
  stage.append(mark);
  const card=document.createElement('div');card.className='stage-card';
  card.innerHTML=`<button type="button" class="stage-trigger" ${locked?'disabled':''} aria-expanded="false" aria-controls="panel-${index+1}" id="trigger-${index+1}">
    <span class="swatch" aria-hidden="true">${number(index)}</span><span class="stage-text"><span class="stage-name">Faixa ${belt.name}</span><span class="stage-category">${belt.category}</span></span><span class="stage-status">${state(index)}</span>${locked?icons.lock:icons.chevron}
    </button><div class="expanded" id="panel-${index+1}" role="region" aria-labelledby="trigger-${index+1}" inert>${locked?'':`<div class="expanded-inner"><div class="focus-content"><div class="focus-copy"><span class="selected-label">${index===current?'SUA FAIXA ATUAL':'PARTE DA SUA HISTÓRIA'}</span><h3>${belt.title}</h3><p>${belt.summary}</p><button type="button" class="primary detail-button">${index===current?'Ver progresso':'Explorar esta faixa'} ${icons.arrow}</button></div><div class="medallion-scene" aria-hidden="true"><div class="medallion"><span>${number(index)}</span></div></div></div></div>`}</div>`;
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
  const panel=createProgressPanel(journeyChecklist(progress,index,payload.atividades),{
    name:belts[index].name,number:number(index),white:index===0,modal,
    next:belts[index+1]?belts[index+1].name:null,
    summary:belts[index].category, achievement:progress.etapas[index].conquista,
    nextReached:progress.etapas[index+1]?.alcancada===true
  });
  if(index===3&&progress.caminho==='freelancer')panel.append(sandboxEvaluationPanel(progress.avaliacoes_sandbox));
  return panel;
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
    ||!/^\/(cursos|encomendas|forum|trilha)(?:\/|$)/.test(action.url)
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
    if(!item||![5,6].includes(item.ordem)||seen.has(item.ordem)
      ||!['andamento','pendente'].includes(item.estado)||typeof item.detalhe!=='string')throw new Error('Atividade indisponível');
    seen.add(item.ordem);return {...item,acao:safeAction(item.acao)};
  });
}
function journeyChecklist(progress,index,activities){
  // O checklist da etapa descreve como conquistar aquela faixa. Na faixa
  // atual, mostramos a atividade que leva à próxima, inclusive no histórico.
  const target=progress.etapas[index+1];
  if(!target)return {disponivel:progress.etapas[index].alcancada,itens:[],observacao:'',concluido:progress.etapas[index].alcancada};
  const sources=[target];
  if(sources.some(step=>!step.checklist))return {disponivel:false,itens:[],observacao:'O checklist está temporariamente indisponível. Tente atualizar em instantes.'};
  const notes=new Set();
  const itens=sources.flatMap(step=>{
    if(step.checklist.observacao)notes.add(step.checklist.observacao);
    const relevantItems=step.checklist.itens;
    return relevantItems.map(item=>{
      if(step.alcancada||progress.caminho!=='freelancer'||![5,6].includes(step.ordem)||item.id!==`criterio-${step.ordem}`)return item;
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
  const title=node(options.modal?'h2':'h3','progress-title',details.concluido?'Percurso concluído.':options.nextReached?'Trabalho já concluído.':options.next?'Meu próximo trabalho.':'Um passo de cada vez.');if(options.modal)title.id='dialog-title';
  const summary=node('p','progress-summary',options.next?(options.nextReached?'Trabalho concluído para conquistar ':'Próximo trabalho para conquistar '):options.summary);
  if(options.next)summary.append(node('strong','',`Faixa ${options.next}`));
  copy.append(node('span','dialog-eyebrow',`FAIXA ${options.name.toLocaleUpperCase('pt-BR')} · CONQUISTA REGISTRADA`));
  if(typeof options.achievement==='string')copy.append(node('p','progress-note achievement-note',`${options.white?'Ponto de partida registrado':'Realização que trouxe esta faixa'}: ${options.achievement}`));
  copy.append(title,summary);
  const badge=node('div','progress-badge');badge.setAttribute('aria-hidden','true');badge.append(node('span','',options.number));
  header.append(copy,badge);panel.append(header);
  if(details.concluido){panel.append(node('p','progress-note','Você concluiu todas as etapas deste percurso. Neste caminho, não há outra faixa por conquistar. Suas conquistas, os XP e o histórico continuam registrados.'));return panel;}
  const available=details.disponivel&&(!options.white||details.itens.length>0);
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
    const detail=blocked&&options.white?`Disponível após concluir “${details.itens[index-1]?.titulo||'Meu motivo'}”.`:item.detalhe;
    content.append(heading,node('p','',detail));
    if(item.acao&&!blocked){
      const action=node('a',state==='concluido'?'checklist-review':'primary checklist-action',state==='concluido'?'Revisar':item.acao.rotulo);
      action.href=item.acao.url;
      if (nativeTaskUrl(item.acao.url)) {
        if (state !== 'concluido' && item.acao.url === '/trilha/inicio/motivo/') action.textContent = 'Definir meus motivos';
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
  const note=node('p','progress-note',options.white?'Conclua uma tarefa e volte à faixa para o próximo passo. Suas respostas e seus arquivos continuam privados.':'Seu progresso acompanha os registros da jornada.');panel.append(note);
  if(details.observacao)panel.append(node('p','checklist-observation',details.observacao));
  return panel;
}

function sandboxEvaluationPanel(evaluations){
  const node=(tag,cls,text)=>{const element=document.createElement(tag);element.className=cls;if(text!==undefined)element.textContent=text;return element;};
  const section=node('section','sandbox-evaluations');
  section.setAttribute('aria-label','Avaliações do Sandbox');
  section.append(node('h4','sandbox-evaluations-title','Avaliação do Sandbox'));
  if(!Array.isArray(evaluations)){
    section.append(node('p','sandbox-evaluations-empty','Não foi possível consultar as avaliações do Sandbox agora. Atualize em instantes.'));
    return section;
  }
  if(!evaluations.length){
    section.append(node('p','sandbox-evaluations-empty','Ainda não há avaliação do Sandbox registrada na sua jornada.'));
    return section;
  }
  const states={pendente:'Aguardando análise',em_analise:'Em análise',falha:'Análise interrompida',concluida:'Análise concluída'};
  const results={atende:'Atende ao pedido',precisa_ajustes:'Precisa de ajustes',inconclusiva:'Avaliação inconclusiva','':''};
  const list=node('ol','sandbox-evaluations-list');
  for(const item of evaluations){
    if(!item||!Number.isInteger(item.versao)||item.versao<1||!Object.hasOwn(states,item.estado)
      ||typeof item.explicacao!=='string'||typeof item.justificativa!=='string'
      ||typeof item.proxima_acao!=='string'||!Object.hasOwn(results,item.resultado)||typeof item.url!=='string'
      ||typeof item.atual!=='boolean'||typeof item.historico!=='boolean'
      ||!item.reconhecimento||typeof item.reconhecimento.estado!=='string'
      ||typeof item.reconhecimento.texto!=='string'){
      section.append(node('p','sandbox-evaluations-empty','Não foi possível apresentar as avaliações do Sandbox agora. Atualize em instantes.'));
      return section;
    }
    const record=node('li','sandbox-evaluation');
    record.append(node('h5','sandbox-evaluation-version',`Versão ${item.versao}${item.atual?' · Atual neste trabalho':''}${item.historico?' · Histórico':''}`));
    record.append(node('p','sandbox-evaluation-state',states[item.estado]));
    if(item.resultado)record.append(node('p','sandbox-evaluation-result',results[item.resultado]));
    if(item.explicacao)record.append(node('p','sandbox-evaluation-explanation',item.explicacao));
    if(item.justificativa)record.append(node('p','sandbox-evaluation-reason',item.justificativa));
    if(item.reconhecimento.texto)record.append(node('p','sandbox-evaluation-recognition',item.reconhecimento.texto));
    if(item.proxima_acao)record.append(node('p','sandbox-evaluation-next',item.proxima_acao));
    if(item.url){
      try{
        const action=safeAction({rotulo:'Abrir trabalho no Sandbox',url:item.url});
        const link=node('a','sandbox-evaluation-link',action.rotulo);
        link.href=action.url;
        if(nativeTaskUrl(action.url))link.addEventListener('click',event=>{
          if(event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button>0)return;
          event.preventDefault();openMotivo(link);
        });
        record.append(link);
      }catch(error){/* Endereço inválido não vira link; a avaliação continua visível. */}
    }
    list.append(record);
  }
  section.append(list);
  return section;
}

function validateProgress(data, context){
  if(data&&(data.pessoa_id!==context.pessoa_id||data.site_id!==context.site_id)){const error=new Error('Sessão alterada');error.invalidIdentity=true;throw error;}
  const integer=value=>Number.isInteger(value)&&value>=0;
  if(!data||data.pessoa_id!==context.pessoa_id||data.site_id!==context.site_id
    ||!Array.isArray(data.etapas)||![7,13].includes(data.etapas.length)
    ||!integer(data.atual_ordem)||data.atual_ordem<1||data.atual_ordem>data.etapas.length
    ||!integer(data.total_cents)||typeof data.meta_escolhida!=='boolean'
    ||(data.meta_cents!==null&&!integer(data.meta_cents))
    ||(data.meta_escolhida&&!(data.meta_cents>0)))throw new Error('Progresso incompleto');
  const steps=[...data.etapas].sort((a,b)=>a.ordem-b.ordem);
  if(steps.some((step,index)=>!step||step.ordem!==index+1||typeof step.alcancada!=='boolean'
      ||(step.nome!==undefined&&typeof step.nome!=='string')||typeof step.conquista!=='string'||(step.feedback!==undefined&&typeof step.feedback!=='string')
      ||(step.meta_cents!==null&&!integer(step.meta_cents))
      ||(step.ordem>=8&&(data.meta_escolhida?step.meta_cents===null:step.meta_cents!==null))
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
        requestJson('/trilha/minha-trilha/'),requestJson('/encomendas/minha-trilha/')
      ]);
      if(journeyResult.status==='rejected')throw journeyResult.reason;
      const progress=validateProgress(journeyResult.value,context);
      celebrateJourney(progress, context);
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
setInterval(()=>{if(!document.hidden)refreshJourney();},30000);
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
function nativeTaskUrl(value) {
  try {
    const url = new URL(value, window.location.origin);
    if(url.origin !== window.location.origin || url.username || url.password || /[\\\s]/.test(value) || url.pathname.includes('..')) return null;
    if(url.pathname === '/trilha/sandbox/') url.pathname = '/encomendas/sandbox/';
    if(url.pathname === '/trilha/fila/') url.pathname = '/encomendas/cliente/';
    if(!(/^\/trilha\/(?:inicio\/(?:motivo|objetivo|item|envio)\/|inicio\/conquista\/[1-4]\/|ciclo\/|recebimentos\/)$/.test(url.pathname)
      || /^\/encomendas\/sandbox\/(?:$|projetos\/[^/]+\/(?:confirmar|aceitar)\/|trabalhos\/[^/]+\/(?:$|(?:arquivo|mensagem|entregar)\/|analise\/[^/]+\/repetir\/))$/.test(url.pathname)
      || /^\/encomendas\/cliente\/(?:$|trabalhos\/[^/]+\/(?:$|(?:confirmar|aceitar|arquivo|mensagem|orientar|entregar)\/))$/.test(url.pathname))) return null;
    return url.href;
  } catch { return null; }
}
let motivoUrl, motivoBusy = false, motivoDirty = false;
async function confirmDiscard() {
  if(motivoScope.querySelector('.discard-question')) return false;
  return new Promise(resolve => {
    const box=document.createElement('section');box.className='discard-question';box.setAttribute('role','alert');
    const text=document.createElement('p');text.textContent='Há respostas ou arquivos ainda não enviados. Quer continuar editando?';
    const stay=document.createElement('button');stay.type='button';stay.textContent='Continuar editando';
    const leave=document.createElement('button');leave.type='button';leave.textContent='Fechar sem salvar';
    const done=value=>{box.remove();resolve(value);};
    stay.onclick=()=>done(false);leave.onclick=()=>done(true);box.append(text,stay,leave);motivoScope.prepend(box);stay.focus();
  });
}
async function loadMotivo(destination, submission) {
  const url=nativeTaskUrl(destination);
  if(!url) {
    if(new URL(destination,window.location.origin).pathname === '/trilha/') { motivoDialog.close();return; }
    throw new Error('Esta atividade não está disponível neste painel.');
  }
  const currentLoad=++motivoLoad;
  if(!submission){motivoController?.destroy?.();motivoController=null;}
  motivoContent.setAttribute('aria-busy','true');
  if(!submission){const loading=document.createElement('p');loading.textContent='Abrindo sua etapa…';loading.setAttribute('role','status');motivoScope.replaceChildren(loading);}
  try {
    const response=await fetch(url,{credentials:'same-origin',cache:'no-store',headers:{'X-Trilha-Painel':'1'},...submission});
    if([401,403].includes(response.status)){motivoScope.replaceChildren();throw new Error('Sua sessão pode ter expirado. Entre novamente na sua conta para continuar.');}
    let component;
    try { component=await response.json(); } catch { throw new Error("Não foi possível abrir ou salvar agora. Suas respostas continuam no formulário; confira antes de tentar novamente."); }
    if(component.componente!=='trilha'||typeof component.html!=='string')throw new Error('Não foi possível abrir esta atividade. Seus registros continuam guardados.');
    if(currentLoad!==motivoLoad||!motivoDialog.open)return;
    const template=document.createElement('template');template.innerHTML=component.html;
    if(template.content.querySelector('iframe,object,embed,script:not([type="application/json"])')||/<!doctype|<html[ >]|<body[ >]/i.test(component.html))throw new Error('O conteúdo desta atividade está indisponível.');
    if(!response.ok){
      const error=template.content.querySelector('[role=alert],.jornada-erro');
      throw new Error(error?.textContent||'Confira os campos antes de enviar novamente. Suas respostas continuam no formulário.');
    }
    const scripts={inicio:'/trilha/faixas-static/inicio.js?v=17',conquista:'/trilha/faixas-static/inicio_conquista.js?v=4',ciclo:'/trilha/faixas-static/ciclo.js?v=2',encomendas:'/trilha/trabalho.js?v=1'};
    if(scripts[component.controlador])await loadMotivoScript(scripts[component.controlador]);
    if(currentLoad!==motivoLoad||!motivoDialog.open)return;
    motivoController?.destroy?.();motivoController=null;motivoDirty=false;
    const base=document.createElement('style');
    base.textContent=':host{display:block;color:#172b48;font:16px/1.6 system-ui,sans-serif}*{box-sizing:border-box}.trilha-modal{padding:20px;min-width:0}.trilha-modal img{max-width:100%}.trilha-modal input:not([type=checkbox]):not([type=radio]),.trilha-modal textarea,.trilha-modal select{max-width:100%}.trilha-modal .page-main{margin:0}.trilha-modal .celebracao{margin-top:0}.motivo-recibo{--papel:#f8faf5;--escuro:#253923;--cinza:#667363;--verde:#58ae17;color:var(--escuro);background:var(--papel)}.painel-status{padding:10px;color:#9b2424;white-space:pre-wrap}.discard-question{position:sticky;top:0;z-index:20;background:#fff4d9;border:1px solid #b79d62;border-radius:12px;padding:16px;margin:10px}.discard-question button{margin:6px;padding:10px;border-radius:8px;cursor:pointer}';
    template.content.querySelectorAll('style').forEach(style=>{style.textContent=style.textContent.replace(/:root\b/g,':host');});
    const wrapper=document.createElement('div');wrapper.className='trilha-modal '+(component.controlador==='inicio'?'inicio-embutido':'');
    wrapper.append(template.content);motivoScope.replaceChildren(base,wrapper);
    motivoUrl=nativeTaskUrl(response.url)||url;
    const host={close:()=>motivoDialog.close(),navigate:loadMotivo,confirmDiscard,scrollTop:()=>{motivoContent.scrollTop=0;}};
    if(component.controlador==='inicio')motivoController=window.iniciarJornada(motivoScope,host);
    else if(component.controlador==='conquista')window.iniciarConquista(motivoScope,host);
    else if(component.controlador==='ciclo')motivoController=window.iniciarCiclo(motivoScope,host);
    else if(component.controlador==='encomendas')motivoController=window.iniciarTrabalhoTrilha(motivoScope,host);
    motivoContent.scrollTop=0;
    const hash=new URL(url).hash;
    if(hash)motivoScope.getElementById(hash.slice(1))?.scrollIntoView({block:'start'});
    refreshJourney();
  } catch(error) {
    if(currentLoad!==motivoLoad||!motivoDialog.open)return;
    let status=motivoScope.querySelector('.painel-status');
    if(!status){status=document.createElement('p');status.className='painel-status';status.setAttribute('role','alert');motivoScope.prepend(status);}
    status.textContent=error.message;
    if(!submission){const retry=document.createElement('button');retry.type='button';retry.textContent='Tentar novamente';retry.onclick=()=>loadMotivo(url);status.append(retry);}
  } finally {if(currentLoad===motivoLoad)motivoContent.removeAttribute('aria-busy');}
}
async function submitTask(event) {
  if(event.defaultPrevented || event.target.closest('#inicio-jornada,#ciclo-criacao'))return;
  const form=event.target;if(form.tagName!=='FORM')return;
  const destination=nativeTaskUrl(form.getAttribute('action')||motivoUrl);
  if(!destination)return;
  event.preventDefault();if(motivoBusy||!form.reportValidity())return;
  const body=new FormData(form);
  if(event.submitter?.name)body.set(event.submitter.name,event.submitter.value);
  motivoBusy=true;
  const controls=Array.from(form.querySelectorAll('button,input,textarea,select'));const disabled=controls.map(c=>c.disabled);controls.forEach(c=>c.disabled=true);
  try{
    const context=JSON.parse(document.querySelector('#trilha-data').textContent);
    const identity=await requestJson('/trilha/minha-trilha/');
    if(identity.pessoa_id!==context.pessoa_id||identity.site_id!==context.site_id){motivoScope.replaceChildren();throw new Error('Sua conta mudou. Reabra a Trilha com a conta em que começou.');}
    if((form.method||'get').toLowerCase()==='get'){
      const url=new URL(destination);for(const [key,value]of body)url.searchParams.set(key,value);await loadMotivo(url.href);
    }else await loadMotivo(destination,{method:'POST',body});
  }catch(error){if([401,403].includes(error.status))motivoScope.replaceChildren();const p=document.createElement('p');p.setAttribute('role','alert');p.textContent=error.message;motivoScope.prepend(p);}
  finally{motivoBusy=false;controls.forEach((c,i)=>c.disabled=disabled[i]);}
}
function openMotivo(opener) {
  if (!motivoDialog) {
    motivoDialog = document.createElement('dialog'); motivoDialog.className = 'motivo-dialog';
    motivoDialog.setAttribute('aria-label', 'Definir meus motivos');
    const close = document.createElement('button'); close.type = 'button'; close.className = 'motivo-close';
    close.textContent = '×'; close.setAttribute('aria-label', 'Fechar meus motivos');
    motivoContent = document.createElement('div'); motivoContent.className = 'motivo-content';
    motivoScope = motivoContent.attachShadow({mode: 'open'});
    const requestClose = async () => { if(motivoBusy)return; if(motivoController?.close)return motivoController.close(); if(motivoDirty&&!await confirmDiscard())return; motivoDialog.close(); };
    close.addEventListener('click', requestClose);
    motivoDialog.addEventListener('cancel', event => { event.preventDefault(); requestClose(); });
    motivoDialog.addEventListener('close', () => {
      motivoLoad++; motivoController?.destroy?.(); motivoController = null; motivoScope.replaceChildren();
      const inDetails = document.querySelector('#detail-dialog').open;
      refreshJourney().then(() => {
        const panel = document.querySelector(inDetails ? '#dialog-panel' : '#timeline');
        (panel?.querySelector(`a[href="${motivoOpener?.getAttribute('href')}"]`) || motivoOpener)?.focus({preventScroll: true});
      });
    });
    motivoScope.addEventListener('input',()=>{motivoDirty=true;});
    motivoScope.addEventListener('submit',submitTask);
    motivoScope.addEventListener('click',async event=>{
      const link=event.target.closest('a');if(!link||event.defaultPrevented||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey||event.button>0||link.hasAttribute('download'))return;
      const href=link.getAttribute('href');if(!href)return;
      if(href.startsWith('#')){event.preventDefault();motivoScope.getElementById(href.slice(1))?.scrollIntoView({block:'start'});return;}
      const destination=nativeTaskUrl(href);
      if(new URL(href,window.location.origin).pathname==='/trilha/'){event.preventDefault();requestClose();return;}
      if(destination){event.preventDefault();if(motivoBusy)return;if(motivoDirty&&!await confirmDiscard())return;loadMotivo(destination);}
      else {link.target='_blank';link.rel='noopener';}
    });
    motivoDialog.append(close, motivoContent); document.body.append(motivoDialog);
  }
  motivoOpener = opener;
  const compromisso = opener.getAttribute('href') === '/trilha/inicio/objetivo/';
  motivoDialog.classList.toggle('compromisso-dialog', compromisso);
  motivoDialog.setAttribute('aria-label', compromisso ? 'Meu compromisso' : (opener.textContent?.trim() || 'Minha atividade'));
  motivoDialog.querySelector('.motivo-close').setAttribute('aria-label', 'Fechar atividade');
  motivoDialog.showModal();
  loadMotivo(opener.getAttribute('href'));
}

function celebrateJourney(progress, context){
  // O recibo da tarefa conduz a esta mesma cerimônia após seu próprio ato.
  if (document.querySelector('.motivo-dialog[open]')) return;
  window.MeshcraftFaixas?.celebrar(progress, context);
}
window.addEventListener('meshcraft:faixa-vista', refreshJourney);
