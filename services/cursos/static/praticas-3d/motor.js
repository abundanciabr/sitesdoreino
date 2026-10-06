const root=document.querySelector('[data-pratica-3d]');
if(root) iniciar();
async function iniciar(){
 const cfg=JSON.parse(document.querySelector('#config-pratica-3d').textContent),$=s=>root.querySelector(s);
 let modelo,receita,id,revisao=0,engine=null,geracao=0,saving=false,dirty=false,primeira=false,modo2d=false,historico=[],concluiu=false;
 const csrf=document.cookie.split('; ').find(x=>x.startsWith('cursos_csrf='))?.split('=').slice(1).join('=')||document.querySelector('[name=csrfmiddlewaretoken]')?.value;
 const status=t=>$('.p3d-status').textContent=t,retorno=t=>$('.p3d-retorno').textContent=t;
 const steps=cfg.configuracao.etapas||['Escolha um item preparado. Veja o resultado que você poderá personalizar.','Escolha a parte e depois a cor. Uma mudança de cada vez; a escolha é sua.','Explore a vista: gire, aproxime e recupere o enquadramento.','Dê um nome ao item e salve na sua conta. Espere a confirmação.','Reconheça suas escolhas no mesmo quadro. Você pode reabrir em Meus itens.'];
 async function evento(tipo){const d=new FormData();d.append('tipo',tipo);d.append('etapa',String(Math.min(receita?.etapa||0,10)));if(csrf)d.append('csrfmiddlewaretoken',decodeURIComponent(csrf));try{await fetch(cfg.eventos,{method:'POST',body:d,credentials:'same-origin',keepalive:true});}catch{}}
 function alterou(){dirty=true;status('Alterações na tela. Clique em Salvar para guardar.');if(!primeira){primeira=true;evento('primeira_mudanca');}}
 function guia(){const n=Math.min(receita.etapa,steps.length-1);$('.p3d-etapa').textContent=`${n+1} de ${steps.length} · ${['Escolher','Personalizar','Explorar','Guardar','Reconhecer'][n]||'Continuar'}`;$('.p3d-instrucao').textContent=steps[n];$('.p3d-cores').classList.toggle('alvo',n===1);$('[data-acao=voltar]').disabled=n===0;$('[data-acao=avancar]').disabled=n===steps.length-1;}
 function selected(){const k=$('.p3d-parte').value;$('.p3d-cor').value=receita.cores[k];$('.p3d-vista').setAttribute('aria-label',`${modelo.nome}, parte ${modelo.partes[k].nome}, cor ${receita.cores[k]}`);}
 function aplicar(){engine?.aplicar(receita);if(modo2d)desenhar2d();selected();}
 function cor(value,nome){const k=$('.p3d-parte').value;historico.push({...receita.cores});receita.cores[k]=value;receita.conferencia=false;aplicar();alterou();retorno(`${modelo.partes[k].nome}: você escolheu ${nome||value}. As outras partes conservam suas cores.`);}
 function desenho(){const colors=receita.cores;const layers=(modelo.camadas||[]).map(l=>`<g fill="${colors[l.parte]}" ${l.parte===modelo.forma.parte?`transform="translate(480 300) scale(${receita.proporcao} 1) translate(-480 -300)"`:''}>${l.svg}</g>`).join('');return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 600" width="960" height="600"><rect width="960" height="600" fill="#182635"/><ellipse cx="480" cy="540" rx="170" ry="22" fill="#101b27"/>${layers}</svg>`;}
 function desenhar2d(){$('.p3d-vista').innerHTML=desenho();}
 function fallback(){modo2d=true;engine?.dispose();engine=null;desenhar2d();$('.p3d-carregando').hidden=false;$('.p3d-carregando').textContent='Vista ilustrada interativa: cores e salvamento disponíveis. Giro e GLB precisam do modo 3D.';$('[data-acao=glb]').disabled=true;root.querySelectorAll('[data-camera]').forEach(b=>b.disabled=true);}
 async function carregar(m,salvo){
  const generation=++geracao;engine?.dispose();engine=null;modo2d=false;modelo=m;
  if(salvo){id=salvo.id;revisao=salvo.revisao;receita=structuredClone(salvo.receita);$('.p3d-nome').value=salvo.titulo;dirty=false;status(`Salvo na sua conta · revisão ${revisao}. Sua personalização foi recuperada.`);}
  else{id=crypto.randomUUID();revisao=0;receita={cores:Object.fromEntries(Object.entries(m.partes).map(([k,v])=>[k,v.cor])),vista:{posicao:[3.5,1.8,7],alvo:[0,0,0]},proporcao:1,etapa:0,conferencia:false,explicacao:''};$('.p3d-nome').value=`Minha ${m.nome}`;dirty=false;status('Suas escolhas ainda não foram salvas.');}
  $('.p3d-proporcao').value=receita.proporcao;$('.p3d-explicacao').value=receita.explicacao||'';historico=[];
  $('.p3d-parte').replaceChildren(...Object.entries(m.partes).map(([k,v])=>{const o=document.createElement('option');o.value=k;o.textContent=v.nome;return o;}));
  $('.p3d-forma').hidden=cfg.dia<2||cfg.pitch;$('.p3d-pedido').hidden=cfg.dia!==3;$('.p3d-forma-nome').textContent=m.forma.nome;$('.p3d-alvo-pedido').textContent=`Parte: ${m.partes[m.forma.parte].nome}. Cor azul: #4b82ed. Proporção: acima de 1.`;
  root.querySelectorAll('.p3d-modelos button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.modelo===m.id+'@'+m.versao)));
  $('.p3d-carregando').hidden=false;$('.p3d-carregando').textContent='Carregando somente o item escolhido…';root.querySelectorAll('[data-camera]').forEach(b=>b.disabled=false);
  guia();selected();
  try{if(new URL(location.href).searchParams.get('vista')==='2d')throw Error('2d');const {criar}=await import('./visualizador.js');const e=await criar($('.p3d-vista'),m,receita,v=>{receita.vista=v;dirty=true;status('Enquadramento alterado. Clique em Salvar para guardar.');},()=>fallback());if(generation!==geracao){e.dispose();return;}engine=e;$('[data-acao=glb]').disabled=false;$('.p3d-carregando').hidden=true;}
  catch{if(generation===geracao)fallback();}
 }
 for(const m of cfg.modelos){const b=document.createElement('button');b.type='button';b.dataset.modelo=m.id+'@'+m.versao;const img=document.createElement('img');img.src=m.miniatura;img.alt='';img.loading='lazy';img.decoding='async';b.append(img,document.createTextNode(m.nome));b.addEventListener('click',async()=>{if(saving)return;if(dirty){retorno('Salve suas escolhas antes de escolher outra base. Use Recomeçar se quiser iniciar outra personalização.');return;}await carregar(m);evento('escolha');});$('.p3d-modelos').append(b);}
 const paleta=[['#4b82ed','azul'],['#36c8ad','verde'],['#ed6682','rosa'],['#e8b44d','dourado'],['#9c79db','roxo'],['#f0f1f5','branco'],['#273449','escuro']];
 for(const [v,n] of paleta){const b=document.createElement('button');b.type='button';b.style.background=v;b.title=n;b.setAttribute('aria-label',`Escolher ${n}`);b.addEventListener('click',()=>cor(v,n));$('.p3d-paleta').append(b);}
 $('.p3d-parte').addEventListener('change',selected);$('.p3d-cor').addEventListener('input',e=>cor(e.target.value));$('.p3d-proporcao').addEventListener('input',e=>{receita.proporcao=Number(e.target.value);receita.conferencia=false;aplicar();alterou();retorno(`${modelo.forma.nome}: proporção ${receita.proporcao.toFixed(2)}. Você mudou a forma, mantendo suas cores.`);});
 $('.p3d-nome').addEventListener('input',alterou);$('.p3d-explicacao').addEventListener('input',()=>{receita.explicacao=$('.p3d-explicacao').value;alterou();});
 root.querySelectorAll('[data-camera]').forEach(b=>b.addEventListener('click',()=>{engine?.mover(b.dataset.camera);alterou();}));
 async function png(){if(engine)return engine.imagem();const url=URL.createObjectURL(new Blob([desenho()],{type:'image/svg+xml'}));try{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=960;c.height=600;c.getContext('2d').drawImage(img,0,0);return await new Promise((res,rej)=>c.toBlob(b=>b?res(b):rej(Error('Não foi possível gerar a imagem.')),'image/png'));}finally{URL.revokeObjectURL(url);}}
 function download(blob,sufixo){const a=document.createElement('a');const u=URL.createObjectURL(blob);a.href=u;a.download=($('.p3d-nome').value||'meu-item').replace(/[^\p{L}\p{N}_ -]/gu,'').slice(0,80)+sufixo;a.click();setTimeout(()=>URL.revokeObjectURL(u),2000);}
 async function salvar(){
  if(saving)return;saving=true;const b=$('[data-acao=salvar]');b.disabled=true;status('Salvando receita e imagem…');
  const frozen=structuredClone(receita);const title=$('.p3d-nome').value;const sentId=id,sentRevision=revisao;
  try{const d=new FormData();d.append('dados',JSON.stringify({id:sentId,revisao:sentRevision,modelo:modelo.id,versao:modelo.versao,titulo:title,receita:frozen}));d.append('imagem',await png(),'personalizacao.png');d.append('csrfmiddlewaretoken',decodeURIComponent(csrf||''));const response=await fetch(cfg.salvar,{method:'POST',body:d,credentials:'same-origin'});let body;try{body=await response.json();}catch{throw Error('A sessão ou a rede não respondeu. Entre novamente ou tente salvar outra vez.');}if(!response.ok){if(body.conflito)$('.p3d-conflito').hidden=false;throw Error(body.erro||'Não foi possível salvar.');}revisao=body.projeto.revisao;dirty=JSON.stringify(frozen)!==JSON.stringify(receita)||title!==$('.p3d-nome').value;status(dirty?'A versão enviada foi salva. Há novas mudanças na tela para salvar.':`Salvo na sua conta · revisão ${revisao}. Pode fechar e reabrir em Meus itens.`);$('.p3d-conflito').hidden=true;concluiu=true;evento('concluir');retorno('Estas cores foram escolhas suas. Sua personalização está guardada.');}
  catch(e){status(`${e.message} Suas escolhas continuam na tela. Clique em Salvar para tentar novamente.`);evento('falha_salvar');}
  finally{saving=false;b.disabled=false;}
 }
 root.addEventListener('click',async e=>{const action=e.target.closest('[data-acao]')?.dataset.acao;if(!action)return;try{
  if(action==='voltar'||action==='avancar'){receita.etapa=Math.max(0,Math.min(steps.length-1,receita.etapa+(action==='avancar'?1:-1)));dirty=true;guia();}
  if(action==='recomecar'){if(saving)return;await carregar(modelo);retorno('Nova personalização na tela. Os itens salvos continuam na sua coleção.');}
  if(action==='desfazer'){if(historico.length){receita.cores=historico.pop();aplicar();alterou();}}
  if(action==='cores-iniciais'){historico.push({...receita.cores});receita.cores=Object.fromEntries(Object.entries(modelo.partes).map(([k,v])=>[k,v.cor]));aplicar();alterou();}
  if(action==='toque'){const ativo=engine?.toque();$('[data-acao=toque]').textContent=ativo?'Voltar à rolagem da aula':'Controlar por toque';}
  if(action==='conferir'){receita.conferencia=receita.cores[modelo.forma.parte].toLowerCase()==='#4b82ed'&&receita.proporcao>1;$('.p3d-conferencia').textContent=receita.conferencia?'Pedido fictício atendido: parte azul e proporção maior. Conte o que mudou.':'Compare: a parte indicada deve estar em azul #4b82ed e a proporção acima de 1. Ajuste e confira de novo.';alterou();evento('compreensao');}
  if(action==='salvar')await salvar();if(action==='copia'){if(saving)return;id=crypto.randomUUID();revisao=0;await salvar();}
  if(action==='imagem')download(await png(),'.png');if(action==='glb'&&engine)download(await engine.glb(),'.glb');
 }catch(e){retorno('Não foi possível baixar agora. Suas escolhas continuam disponíveis.');}});
 const saved=cfg.projeto;const m=cfg.modelos.find(m=>saved&&m.id===saved.modelo&&m.versao===saved.versao)||cfg.modelos[0];
 if(!m){status('A escola está preparando as bases desta atividade.');return;}
 await carregar(m,saved);evento(saved?'recuperar':'inicio');
 addEventListener('pagehide',()=>{if(!concluiu)evento('abandono');engine?.dispose();});
}
