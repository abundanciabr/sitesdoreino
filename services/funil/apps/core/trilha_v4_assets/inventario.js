'use strict';
const context=JSON.parse(document.querySelector('#trilha-data').textContent);
const endpoint='/conquistas/inventario/';
let data=null, busy=false;
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
  const first=data.etapas.find(e=>e.ordem===2), hasFile=data.anexos.some(a=>a.passo===2);
  q('.save-file').hidden=first.alcancada;
  q('#first-state').textContent=first.alcancada?'CONCLUÍDO':hasFile?'ARQUIVO GUARDADO':'PENDENTE';
  q('#first-file').required=first.alcancada||!hasFile;
  q('#first-form [name=acao]').value=first.alcancada?'anexo':'declaracao';
  q('#first-submit').textContent=first.alcancada?'Guardar outro arquivo →':'Concluí meu item 3D →';
  q('#first-declaration').textContent=first.alcancada?'Sua conclusão já está registrada. Os arquivos ficam guardados aqui.':'“Concluí meu primeiro item 3D e consigo mostrar o resultado.”';
  fileList(q('#first-files'),2);
  q('#current-belt').textContent=`Faixa atual: ${data.etapas.find(e=>e.ordem===data.atual_ordem).nome}`;
  q('#steps').replaceChildren();data.etapas.forEach(e=>{const li=el('li',e.nome);li.className=e.alcancada?'done':'pending';li.append(el('small',e.alcancada?'Conquista registrada':e.ordem===data.atual_ordem+1?'Próxima conquista':'Pendente'));q('#steps').append(li);});
  q('#goal').value=data.meta_cents===null?'':(data.meta_cents/100).toFixed(2);q('#purpose').value=data.proposito;
  q('#received-total').textContent=`${data.total} em recebimentos reconhecidos pelo conteúdo dos prints.`;
  q('#receipts').replaceChildren();data.recebimentos.forEach(r=>q('#receipts').append(el('li',`${r.valor} · ${r.estado} · ${r.data}`)));
  q('#history').replaceChildren();data.historico.forEach(r=>{const li=el('li',r.texto);li.append(el('time',new Date(r.criado_em).toLocaleString('pt-BR')));q('#history').append(li);});
  if(!data.historico.length)q('#history').append(el('li','Seus registros aparecerão aqui conforme você avançar.'));
  q('#deliveries').replaceChildren();
  [3,4].forEach(ordem=>{const etapa=data.etapas.find(e=>e.ordem===ordem), details=document.createElement('details');details.append(el('summary',`${ordem===3?'Minha prática no Sandbox':'Meu trabalho real na Fila'} · ${etapa.alcancada?'Concluído':'Pendente'}`));
    details.append(el('p',etapa.conquista));const link=el('a',ordem===3?'Abrir Sandbox →':'Abrir Fila →');link.href=ordem===3?'/encomendas/sandbox/':'/encomendas/fila/';link.className='text-link';details.append(link);
    const files=el('ul','');files.className='files';fileList(files,ordem);details.append(files);
    const form=document.createElement('form');
    for(const [name,value] of Object.entries({acao:etapa.alcancada?'anexo':'declaracao',passo:String(ordem),estado:'feito'})){const input=document.createElement('input');input.type='hidden';input.name=name;input.value=value;form.append(input);}
    const label=el('label',etapa.alcancada?'Guardar um arquivo desta entrega':'Arquivo da entrega (opcional)');label.htmlFor=`file-${ordem}`;const input=document.createElement('input');input.type='file';input.name='arquivo';input.id=label.htmlFor;input.accept=q('#first-file').accept;input.required=etapa.alcancada;form.append(label,input);
    const button=el('button',etapa.alcancada?'Guardar arquivo':'Concluí e entreguei este trabalho');button.className='primary';button.type='submit';form.append(button);form.addEventListener('submit',submit);details.append(form);q('#deliveries').append(details);
  });
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
