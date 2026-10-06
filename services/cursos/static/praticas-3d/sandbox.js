import {criar} from './visualizador.js';
const root=document.querySelector('[data-sandbox-3d]');
if(root) iniciar().catch(()=>{root.querySelector('[data-status]').textContent='Não foi possível carregar agora. Reabra esta página para tentar novamente.';});
async function iniciar(){
 const $=s=>root.querySelector(s),base='/cursos/static/praticas-3d/',catalog=await (await fetch(base+'catalogo.json')).json(),receitas=new Map();
 let engine=null,model,recipe,generation=0,fallback=false;
 const status=t=>$('[data-status]').textContent=t;
 function svg(){return `<svg xmlns="http://www.w3.org/2000/svg" width="960" height="600" viewBox="0 0 960 600"><rect width="960" height="600" fill="#182635"/>${(model.camadas||[]).map(l=>`<g fill="${recipe.cores[l.parte]}">${l.svg}</g>`).join('')}</svg>`;}
 function apply(){engine?.aplicar(recipe);if(fallback)$('[data-vista]').innerHTML=svg();}
 function illustrated(){engine?.dispose();engine=null;fallback=true;apply();root.querySelectorAll('[data-camera], [data-action="glb"], [data-action="touch"]').forEach(b=>b.disabled=true);$('[data-scale]').disabled=true;status('Vista ilustrada: personalize as cores e baixe a imagem. O modelo GLB e o fonte Blender continuam disponíveis abaixo.');}
 async function select(slug){
  const m=catalog.find(m=>m.projeto_sandbox===slug);if(!m)return;
  const turn=++generation;engine?.dispose();engine=null;fallback=false;model={...m,url:base+`modelos/${m.id}/v${m.versao}/base.glb`};
  recipe=receitas.get(slug)||{cores:Object.fromEntries(Object.entries(m.partes).map(([k,v])=>[k,v.cor])),proporcao:1,vista:{posicao:[3.5,1.8,7],alvo:[0,0,0]}};receitas.set(slug,recipe);
  $('[data-title]').textContent=m.nome;$('[data-parts]').replaceChildren(...Object.entries(m.partes).map(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v.nome;return o;}));$('[data-color]').value=recipe.cores[$('[data-parts]').value];$('[data-scale]').value=recipe.proporcao;$('[data-scale-label]').textContent=m.forma.nome;
  $('[data-source]').href=base+`modelos/${m.id}/v${m.versao}/fonte.blend`;$('[data-original]').href=model.url;
  root.querySelectorAll('button,input').forEach(b=>b.disabled=false);$('[data-action="touch"]').textContent='Controlar por toque';status('Carregando modelo 3D…');
  const host=document.createElement('div');host.style.cssText='width:100%;height:100%';$('[data-vista]').replaceChildren(host);
  try{if(new URL(location.href).searchParams.get('vista')==='2d')throw Error('2d');const e=await criar(host,model,recipe,v=>{if(turn===generation)recipe.vista=v;},()=>{if(turn===generation)illustrated();});if(turn!==generation){e.dispose();return;}engine=e;status('Gire o modelo e personalize suas partes. Baixe sua versão para continuar no Blender.');}catch{if(turn===generation)illustrated();}
 }
 function download(blob,ext){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=model.id+ext;a.click();setTimeout(()=>URL.revokeObjectURL(url),2000);}
 $('[data-parts]').addEventListener('change',()=>{$('[data-color]').value=recipe.cores[$('[data-parts]').value];});
 $('[data-color]').addEventListener('input',e=>{recipe.cores[$('[data-parts]').value]=e.target.value;apply();});
 $('[data-scale]').addEventListener('input',e=>{recipe.proporcao=Number(e.target.value);apply();});
 root.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>engine?.mover(b.dataset.camera)));
 root.addEventListener('click',async e=>{const action=e.target.closest('[data-action]')?.dataset.action;if(!action)return;try{
  if(action==='touch'){const active=engine?.toque();$('[data-action="touch"]').textContent=active?'Voltar à rolagem da página':'Controlar por toque';}
  if(action==='reset'){recipe.cores=Object.fromEntries(Object.entries(model.partes).map(([k,v])=>[k,v.cor]));recipe.proporcao=1;$('[data-scale]').value=1;$('[data-color]').value=recipe.cores[$('[data-parts]').value];apply();}
  if(action==='glb'&&engine)download(await engine.glb(),'.glb');
  if(action==='png'){
   if(engine)download(await engine.imagem(),'.png');
   else{const url=URL.createObjectURL(new Blob([svg()],{type:'image/svg+xml'}));try{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=960;c.height=600;c.getContext('2d').drawImage(img,0,0);download(await new Promise(r=>c.toBlob(r,'image/png')),'.png');}finally{URL.revokeObjectURL(url);}}
  }
 }catch{status('O download não terminou. Suas escolhas continuam nesta tela; tente novamente.');}});
 document.querySelectorAll('[data-escolher], [data-brief], [data-confirmar], [data-referencia]').forEach(b=>b.addEventListener('click',()=>select(b.dataset.escolher||b.dataset.brief||b.dataset.confirmar||b.dataset.referencia)));
 addEventListener('pagehide',()=>{generation++;engine?.dispose();});
 await select(document.querySelector('[data-escolher][aria-pressed="true"]')?.dataset.escolher);
}
