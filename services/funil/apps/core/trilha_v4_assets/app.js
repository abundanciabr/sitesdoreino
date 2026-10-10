'use strict';
function renderJourney(payload){
const icons = {arrow:'<svg aria-hidden="true"><use href="#arrow"/></svg>',check:'<svg aria-hidden="true"><use href="#check"/></svg>',chevron:'<svg aria-hidden="true"><use href="#chevron"/></svg>',lock:'<svg class="lock-icon" aria-hidden="true"><use href="#lock"/></svg>'};
const belts = [
  {name:'Branca',short:'Branca',category:'O começo de tudo',title:'Toda criação começa com curiosidade.',summary:'Conheça seu ambiente e dê o primeiro passo na modelagem 3D.',color:'#e2e2e7',wash:'#f6f6f8',tone:'#66666d',ink:'#73737a',tasks:[['Prepare seu ambiente','Configure as ferramentas para começar a modelar.'],['Conheça o painel','Encontre os conteúdos que vão acompanhar sua jornada.'],['Comece pelo essencial','Explore os fundamentos da modelagem 3D.']]},
  {name:'Amarela',short:'Amarela',category:'Seu primeiro modelo',title:'Uma ideia. Sua primeira forma.',summary:'Leve o que aprendeu para o Blender e crie seu primeiro item 3D.',color:'#e9c34b',wash:'#fdf9e9',tone:'#8c6b0b',ink:'#735d17',tasks:[['Escolha seu item','Comece com uma forma simples para colocar os fundamentos em prática.'],['Crie no Blender','Modele seu primeiro item e revise o resultado.'],['Prepare para avaliação','Organize o arquivo para receber orientações.']]},
  {name:'Azul',short:'Azul',category:'Prática no Sandbox',title:'Experimente. Ajuste. Evolua.',summary:'Um espaço para testar seu modelo e descobrir o que pode ficar melhor.',color:'#6299de',wash:'#eef5fc',tone:'#2b65a6',ink:'#f9fcff',tasks:[['Importe seu modelo','Leve sua criação para o ambiente de prática.'],['Ajuste a escala','Confira como o objeto se comporta no ambiente.'],['Revise o resultado','Faça os ajustes antes de trabalhar em um projeto real.']]},
  {name:'Vermelha',short:'Vermelha',category:'Trabalho real',title:'Sua criação encontra o mundo.',summary:'Um projeto real. Um novo desafio. A hora de transformar prática em entrega.',color:'#dc6263',wash:'#fdf0ef',tone:'#b44348',ink:'#fff9f9',tasks:[['Escolha uma encomenda','Leia o pedido e entenda o que o projeto precisa.'],['Dê forma ao projeto','Modele seguindo os requisitos e revise sua entrega.'],['Envie para análise','Prepare o arquivo para a avaliação da equipe.']]},
  {name:'Verde',short:'Verde',category:'Primeiro dinheiro',title:'O primeiro resultado tem outro valor.',summary:'Seu primeiro trabalho aprovado e o primeiro pagamento recebido.',color:'#65af88',wash:'#eef8f2',tone:'#317150',ink:'#f5fff9',tasks:[['Trabalho aprovado','Acompanhe a conclusão da avaliação do projeto.'],['Pagamento recebido','Este marco representa o recebimento pelo trabalho realizado.']],note:'Os valores e recebimentos não estão conectados nesta prévia. Metas não são garantia de renda.'},
  {name:'Marrom',short:'Marrom',category:'Consistência',title:'O seu melhor ganha continuidade.',summary:'Transforme a primeira experiência em uma prática que continua evoluindo.',color:'#ae8b73',wash:'#f8f3ef',tone:'#795b46',ink:'#fffbf7',tasks:[['Continue criando','Dê continuidade à prática e aos seus projetos.'],['Acompanhe sua meta','O plano apresenta R$ 25 como marco desta faixa.']],note:'A forma de apuração da meta ainda será definida. Esta prévia não registra faturamento.'},
  ...Array.from({length:7},(_,i)=>({name:`Preta ${i+1}º grau`,short:`${i+1}º grau`,category:i===6?'Mestre modelador':`Maestria · Grau ${String(i+1).padStart(2,'0')}`,title:i===6?'Sua evolução abre novos caminhos.':`Um novo grau. Mais possibilidades.`,summary:i===6?'Um portfólio de alto valor. Um horizonte de novas criações.':`O ${i+1}º grau da Faixa Preta é mais um capítulo da sua jornada na modelagem.`,color:'#49494f',wash:'#f2f2f5',tone:'#585860',ink:'#f6f6fa',tasks:i===6?[['Seu portfólio','O plano propõe domínio de malhas complexas e um portfólio de alto valor.'],['Seu horizonte','A meta apresentada no plano é de R$ 2.000.']]:[['O próximo capítulo','Os critérios específicos deste grau ainda serão definidos para a versão real.']],note:i===6?'A apuração da meta ainda será definida. Metas não garantem renda.':'Esta etapa demonstra a navegação e o visual. Nenhum critério novo de progressão foi estabelecido.'}))
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
  belt.tasks=[['Resultado desta etapa',step.conquista],['Situação registrada',step.alcancada?'Esta etapa consta como alcançada na sua jornada.':'Esta etapa ainda não consta como alcançada.']];
  if(index>=4){
    belt.tasks.push(['Recebimentos confirmados',money(progress.total_cents)]);
    if(index>=5&&progress.meta_escolhida){
      belt.tasks.push(['Meta desta etapa',money(step.meta_cents)]);
      belt.tasks.push(['Falta para esta etapa',money(Math.max(0,step.meta_cents-progress.total_cents))]);
    }
  }
  if(step.alcancada_em){
    const when=new Date(step.alcancada_em);
    if(!Number.isNaN(when.getTime()))belt.tasks.push(['Data registrada',new Intl.DateTimeFormat('pt-BR',{dateStyle:'medium',timeZone:'America/Sao_Paulo'}).format(when)]);
  }
  belt.note='Seu progresso acompanha os registros da sua jornada. Explorar esta trilha não altera esses registros.';
});
let selected = current;
const timeline = document.querySelector('#timeline');
const dock = document.querySelector('#dock');
const previous = document.querySelector('#previous');
const next = document.querySelector('#next');
const dialog = document.querySelector('#detail-dialog');
const stages = [];
const dockButtons = [];
let dialogOpener;
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
    card.querySelector('.detail-button').addEventListener('click',event=>openDetails(index,event.currentTarget));
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
function openDetails(index,opener){
  if(!reached(index))return;
  const belt=belts[index];dialogOpener=opener;
  dialog.style.setProperty('--accent',belt.color);dialog.style.setProperty('--swatch-ink',belt.ink);
  document.querySelector('#dialog-eyebrow').textContent=`Faixa ${index+1} de 13 · ${state(index)}`;
  document.querySelector('#dialog-number').textContent=number(index);
  document.querySelector('#dialog-title').textContent=`Faixa ${belt.name}`;
  document.querySelector('#dialog-summary').textContent=belt.summary;
  const tasks=document.querySelector('#task-list');tasks.replaceChildren();
  belt.tasks.forEach(([title,body],i)=>{
    const task=document.createElement('li');const n=document.createElement('span');n.className='task-number';n.textContent=i+1;
    const text=document.createElement('div');const heading=document.createElement('strong');heading.textContent=title;const description=document.createElement('p');description.textContent=body;text.append(heading,description);task.append(n,text);tasks.append(task);
  });
  document.querySelector('#dialog-note').textContent=belt.note;
  dialog.showModal();dialog.scrollTop=0;
}
function closeDetails(){dialog.close();}
dialog.addEventListener('close',()=>dialogOpener?.focus({preventScroll:true}));
document.querySelector('.dialog-close').addEventListener('click',closeDetails);
document.querySelector('#back-to-journey').addEventListener('click',closeDetails);
dialog.addEventListener('click',event=>{if(event.target!==dialog)return;const box=dialog.getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)closeDetails();});
document.querySelector('#resume').addEventListener('click',()=>select(current,true));
previous.addEventListener('click',()=>select(adjacent(-1),true));
next.addEventListener('click',()=>select(adjacent(1),true));
dock.addEventListener('keydown',event=>{
  const keys={ArrowRight:adjacent(1),ArrowLeft:adjacent(-1),Home:available[0],End:available[available.length-1]};
  if(Object.hasOwn(keys,event.key)){event.preventDefault();select(keys[event.key],true);dockButtons[selected].focus({preventScroll:true});}
});
select(current,false);

  document.querySelector('#resume').disabled=false;
  document.querySelector('.hero-object').removeAttribute('aria-busy');
  document.querySelector('.object-caption').textContent='SEU MOMENTO ATUAL';
}

function validateProgress(data, context){
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
    ||Math.max(...steps.filter(step=>step.alcancada).map(step=>step.ordem))!==data.atual_ordem)
    throw new Error('Progresso incompleto');
  return {...data, etapas:steps};
}

async function loadJourney(){
  const context=JSON.parse(document.querySelector('#trilha-data').textContent);
  try{
    const response=await fetch('/conquistas/minha-trilha/',{
      credentials:'same-origin',cache:'no-store',headers:{Accept:'application/json'}
    });
    if(response.status===403){window.location.replace('/login?next=%2Ftrilha%2F');return;}
    if(!response.ok)throw new Error('Consulta indisponível');
    const progress=validateProgress(await response.json(),context);
    renderJourney({...context,progresso:progress});
  }catch(error){
    document.querySelector('.hero-object').removeAttribute('aria-busy');
    document.querySelector('.hero-object').setAttribute('aria-label','Progresso indisponível');
    document.querySelector('.object-caption').textContent='PROGRESSO INDISPONÍVEL';
    document.querySelector('.explore-hint').textContent='Não foi possível consultar seu progresso agora. Recarregue a página para tentar novamente.';
  }
}
loadJourney();
