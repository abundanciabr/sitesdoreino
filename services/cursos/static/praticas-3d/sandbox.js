import {criar} from './estudio.js?v=3';
const root=document.querySelector('[data-sandbox-3d]');
if(root) iniciar().catch(()=>{root.querySelector('[data-status]').textContent='Não foi possível carregar agora. Reabra esta página para tentar novamente.';});
async function iniciar(){
 const $=s=>root.querySelector(s),base='/cursos/static/praticas-3d/',response=await fetch(base+'catalogo.json?v=3');
 if(!response.ok)throw Error('Catálogo indisponível');
 const catalog=await response.json(),receitas=new Map();
 const variants=catalog[0].variantes,requested=new URL(location.href).searchParams.get('variante');
 let variantId=variants.some(v=>v.id===requested)?requested:'azul-laranja';
 let engine=null,model,recipe,generation=0,fallback=false,slugAtual;
 const status=t=>$('[data-status]').textContent=t;
 const folder=(m,v)=>base+`modelos/${m.id}/v${m.versao}/`+(v?.pasta||'');
 function updateThumbnails(){
  const current=new URL(location.href);current.searchParams.set('variante',variantId);history.replaceState(null,'',current);
  for(const m of catalog){
   const v=m.variantes.find(v=>v.id===variantId),src=folder(m,v)+'miniatura.png';
   for(const card of document.querySelectorAll(`[data-projeto="${m.projeto_sandbox}"], [data-summary="${m.projeto_sandbox}"]`)){
    const img=card.querySelector('img');if(img){img.src=src;img.classList.add('modelo-render');}
   }
  }
  const icons={'espadas':'fuzil-nova','pets':'raposa-lume','cabelos':'cabelo-vento','chapeus':'chapeu-astral','personagens':'robo-pingo'};
  for(const [name,id] of Object.entries(icons)){
   const m=catalog.find(m=>m.id===id),v=m.variantes.find(v=>v.id===variantId),icon=document.querySelector('.art-'+name);
   if(icon){icon.style.backgroundImage=`url("${folder(m,v)}miniatura.png")`;icon.style.backgroundSize='cover';icon.style.backgroundPosition='center';icon.style.borderRadius='8px';}
  }
  const decor=document.querySelector('.header-scene');if(decor){decor.style.background='none';decor.style.display='none';}
  document.querySelectorAll('.category-card').forEach(a=>{const url=new URL(a.href);url.searchParams.set('variante',variantId);a.href=url.href;});
  root.querySelectorAll('[data-variante]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.variante===variantId)));
 }
 function svg(){return `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600"><rect width="960" height="600" fill="#252a31"/>${(model.camadas||[]).map(l=>`<g fill="${recipe.cores[l.parte]}">${l.svg}</g>`).join('')}</svg>`;}
 function apply(){engine?.aplicar(recipe);if(fallback)$('[data-vista]').innerHTML=svg();}
 function illustrated(){engine?.dispose();engine=null;fallback=true;apply();root.querySelectorAll('[data-camera], [data-action="glb"], [data-action="touch"], [data-action="mesh"]').forEach(b=>b.disabled=true);$('[data-scale]').disabled=true;status('Vista ilustrada: personalize as cores e baixe a imagem. O modelo GLB e o fonte Blender continuam disponíveis abaixo.');}
 async function select(slug,selected=variantId){
  const m=catalog.find(m=>m.projeto_sandbox===slug);if(!m)return;
  variantId=selected;slugAtual=slug;updateThumbnails();
  const variant=m.variantes.find(v=>v.id===variantId)||m.variantes[0],turn=++generation;
  engine?.dispose();engine=null;fallback=false;
  const path=folder(m,variant);
  model={...m,partes:Object.fromEntries(Object.entries(variant.partes||m.partes).map(([k,v])=>[k,{...v,cor:variant.cores[k]}])),camadas:variant.camadas,malha:variant.malha,url:path+'base.glb',variante:variantId};
  const key=slug+'@'+variantId;
  recipe=receitas.get(key)||{cores:{...variant.cores},proporcao:1,vista:{posicao:[3.5,1.8,7],alvo:[0,0,0]}};receitas.set(key,recipe);
  $('[data-title]').textContent=m.nome;
  $('[data-description]').textContent=m.descricao;
  $('[data-variant-title]').textContent=variant.nome;
  $('[data-triangles]').textContent=new Intl.NumberFormat('pt-BR').format(model.malha.triangulos)+' triângulos · Normais planas · Cores sólidas';
  $('[data-parts]').replaceChildren(...Object.entries(model.partes).map(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v.nome;return o;}));
  $('[data-color]').value=recipe.cores[$('[data-parts]').value];$('[data-scale]').value=recipe.proporcao;$('[data-scale-label]').textContent=m.forma.nome;
  $('[data-source]').href=path+'fonte.blend';$('[data-source]').download=m.id+'-'+variantId+'.blend';
  $('[data-original]').href=model.url;$('[data-original]').download=m.id+'-'+variantId+'.glb';
  root.querySelectorAll('button,input').forEach(b=>b.disabled=false);$('[data-action="glb"]').disabled=true;$('[data-action="touch"]').textContent='Controlar por toque';
  $('[data-action="mesh"]').textContent='Ver malha';$('[data-action="mesh"]').setAttribute('aria-pressed','false');status('Carregando modelo 3D…');
  const host=document.createElement('div');host.style.cssText='width:100%;height:100%';$('[data-vista]').replaceChildren(host);
  try{
   if(new URL(location.href).searchParams.get('vista')==='2d')throw Error('2d');
   const e=await criar(host,model,recipe,v=>{if(turn===generation)recipe.vista=v;},()=>{if(turn===generation)illustrated();});
   if(turn!==generation){e.dispose();return;}
   engine=e;$('[data-action="glb"]').disabled=false;status('Gire o modelo e personalize suas partes. Baixe sua versão para continuar no Blender.');
  }catch{if(turn===generation)illustrated();}
 }
 function download(blob,ext){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=model.id+'-'+variantId+ext;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
 $('[data-parts]').addEventListener('change',()=>{$('[data-color]').value=recipe.cores[$('[data-parts]').value];});
 $('[data-color]').addEventListener('input',e=>{recipe.cores[$('[data-parts]').value]=e.target.value;apply();});
 $('[data-scale]').addEventListener('input',e=>{recipe.proporcao=Number(e.target.value);apply();});
 root.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>engine?.mover(b.dataset.camera)));
 root.querySelectorAll('[data-variante]').forEach(b=>b.addEventListener('click',()=>select(slugAtual,b.dataset.variante)));
 root.addEventListener('click',async e=>{
  const action=e.target.closest('[data-action]')?.dataset.action;if(!action)return;
  try{
   if(action==='touch'){const active=engine?.toque();$('[data-action="touch"]').textContent=active?'Voltar à rolagem da página':'Controlar por toque';}
   if(action==='mesh'){const active=engine?.malha();$('[data-action="mesh"]').textContent=active?'Ver materiais':'Ver malha';$('[data-action="mesh"]').setAttribute('aria-pressed',String(Boolean(active)));}
   if(action==='reset'){recipe.cores=Object.fromEntries(Object.entries(model.partes).map(([k,v])=>[k,v.cor]));recipe.proporcao=1;$('[data-scale]').value=1;$('[data-color]').value=recipe.cores[$('[data-parts]').value];apply();}
   if(action==='glb'&&engine)download(await engine.glb(),'.glb');
   if(action==='png'){
    if(engine)download(await engine.imagem(),'.png');
    else{
     const url=URL.createObjectURL(new Blob([svg()],{type:'image/svg+xml'}));
     try{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=960;c.height=600;c.getContext('2d').drawImage(img,0,0);download(await new Promise(r=>c.toBlob(r,'image/png')),'.png');}finally{URL.revokeObjectURL(url);}
    }
   }
  }catch{status('O download não terminou. Suas escolhas continuam nesta tela; tente novamente.');}
 });
 document.querySelectorAll('[data-escolher], [data-brief], [data-confirmar], [data-referencia]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.escolher||b.dataset.brief||b.dataset.confirmar||b.dataset.referencia)));
 for(const figure of document.querySelectorAll('[data-reference-project]')){
  const m=catalog.find(m=>m.projeto_sandbox===figure.dataset.referenceProject);if(!m)continue;
  const grid=document.createElement('div');grid.className='variant-reference-grid';
  for(const v of m.variantes){
   const button=document.createElement('button');button.type='button';button.className='variant-reference';button.setAttribute('aria-label',m.nome+' · '+v.nome);
   const img=document.createElement('img');img.src=folder(m,v)+'miniatura.png';img.alt=m.nome+' em '+v.nome.toLowerCase();img.loading='lazy';img.decoding='async';
   button.append(img,document.createTextNode(v.nome));button.addEventListener('click',()=>{variantId=v.id;document.querySelector(`[data-escolher="${m.projeto_sandbox}"]`).click();root.scrollIntoView({behavior:'smooth',block:'start'});});grid.append(button);
  }
  figure.querySelector('img')?.replaceWith(grid);const label=figure.querySelector('figcaption span');if(label)label.textContent='Três versões renderizadas do próprio modelo 3D';
 }
 addEventListener('pagehide',()=>{generation++;engine?.dispose();});
 await select(document.querySelector('[data-escolher][aria-pressed="true"]')?.dataset.escolher);
}
