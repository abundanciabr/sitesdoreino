const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/inicio.js'),'utf8');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

function record(overrides={}){
  return {pessoa_id:'aluna-a',site_id:'escola-a',csrf:'csrf-teste',revisao:3,
    inicio:{motivo:'ugc',motivo_pessoal:'Motivo reservado',sonho:'SONHO PRIVADO',objetivo:'Criar um chapéu',
      compromisso:'COMPROMISSO PRIVADO',confirmado_em:'2026-10-10T12:00:00Z',apoio:'guiado',
      pratica:'Comece com uma forma simples.',motivos:[{valor:'ugc',nome:'Itens próprios'}]},
    etapas:[{ordem:1,alcancada:true},{ordem:2,alcancada:false}],anexos:[],...overrides};
}
function file(overrides={}){
  return {id:1,passo:2,nome:'obra.obj',url:'/conquistas/inventario/arquivos/1/',
    criado_em:'2026-10-10T12:00:00Z',aprendi:'Minha tentativa',duvida:'Como suavizar a borda?',...overrides};
}

async function page(step,initial=record(),hash=''){
  const nodes=[];
  class Element {
    constructor(tag,id=''){this.tagName=tag;this.id=id;this.dataset={};this.children=[];this.events={};this.value='';this.files=[];this.hidden=false;this.text='';nodes.push(this);}
    get textContent(){return this.text+this.children.map(n=>n.textContent||'').join('');}
    set textContent(value){this.text=String(value);this.children=[];}
    append(...children){children.forEach(child=>{child.parent=this;this.children.push(child);});}
    replaceChildren(...children){this.text='';this.children=[];this.append(...children);}
    setAttribute(name,value){this[name]=value;}
    addEventListener(type,handler){(this.events[type]??=[]).push(handler);}
    after(node){node.parent=this.parent;}
    remove(){this.removed=true;}
    focus(){this.focused=true;}
    select(){}
    scrollIntoView(){this.scrolledWhileVisible=!nodes.find(node=>node.id==='inicio-conteudo').hidden;}
  }
  const add=(id,tag='div')=>new Element(tag,'inicio-'+id);
  const root=add('jornada');root.dataset={api:'/conquistas/inventario/',conquistas:'/conquistas/',proxima:step==='motivo'?'/conquistas/inicio/objetivo/':'/conquistas/inicio/item/'};
  const summaries=[new Element('small'),new Element('small'),new Element('small')];
  root.querySelector=selector=>summaries[Number(selector.match(/\d/)[0])-1];
  root.querySelectorAll=selector=>nodes.filter(node=>selector==='a'?node.tagName==='a':['button','input','textarea','select'].includes(node.tagName));
  const form=add('form-'+step,'form');form.elements={};
  const fields=step==='motivo'?['motivo_pessoal']:step==='plano'?['sonho','objetivo','quando','obstaculo','plano_b','compromisso','apoio']:['arquivo','aprendi','duvida'];
  fields.forEach(name=>{const node=add(name,name==='arquivo'?'input':'textarea');node.name=name;form.elements[name]=node;form.append(node);});
  form.reset=()=>Object.values(form.elements).forEach(node=>{node.value='';node.files=[];});
  ['status','conteudo','recarregar','comparacao'].filter(id=>id!=='comparacao').forEach(id=>add(id,id==='recarregar'?'button':'div'));
  if(step==='motivo'){const options=add('opcoes');form.append(options);}
  if(step==='plano'){add('confirmacao');add('sugestao','button');}
  if(step==='item'){
    ['objetivo-salvo','pratica','apoio-texto','concluir','item-estado','obra','destaque','versoes','obra-legenda','pedir-ajuda','ajuda','mensagem','copiar'].forEach(id=>add(id));
  }
  const byId=id=>nodes.find(node=>node.id==='inicio-'+id&&!node.removed)||null;
  byId('conteudo').hidden=true;
  if(step==='item')byId('ajuda').hidden=true;
  class FormData {
    constructor(target){this.values=new Map(Object.values(target.elements).map(node=>[node.name,node.name==='arquivo'?node.files[0]||'':node.value]));nodes.filter(n=>n.name==='motivo'&&n.checked).forEach(n=>this.set(n.name,n.value));}
    set(key,value){this.values.set(key,value);}
    get(key){return this.values.get(key);}
  }
  const calls=[],redirects=[],copied=[],windowEvents={};
  let current=initial,nextError=null;
  const context=vm.createContext({FormData,location:{hash},
    document:{getElementById:id=>nodes.find(node=>node.id===id&&!node.removed)||null,createElement:tag=>new Element(tag),createTextNode:text=>{const node=new Element('#text');node.textContent=text;return node;}},
    window:{location:{assign:dest=>redirects.push(dest)},addEventListener:(type,handler)=>{windowEvents[type]=handler;}},
    navigator:{clipboard:{writeText:async text=>copied.push(text)}},
    fetch:async(url,options)=>{calls.push({url,options});if(nextError){const error=nextError;nextError=null;if(error instanceof Error)throw error;return error;}return {ok:true,status:200,json:async()=>structuredClone(current)};}
  });
  vm.runInContext(source,context);await tick();
  const fire=async(node,type,values={})=>{for(const handler of node.events[type]||[])await handler({preventDefault(){},...values});await tick();};
  return {byId,form,calls,redirects,copied,summaries,fire,
    setRecord:value=>{current=value;},fail:value=>{nextError=value;},
    reopen:async()=>{windowEvents.pageshow({persisted:true});await tick();},
    submit:async value=>fire(form,'submit',{submitter:{value}}),
  };
}

test('motivo salvo é retomado e continuar envia identidade, revisão e CSRF antes de navegar',async()=>{
 const ui=await page('motivo');
 assert.equal(ui.form.elements.motivo_pessoal.value,'Motivo reservado');
 assert.equal(ui.byId('conteudo').hidden,false);
 await ui.submit('continuar');
 const post=ui.calls.find(call=>call.options.method==='POST');
 assert.equal(post.options.body.get('acao'),'inicio-motivo');
 assert.equal(post.options.body.get('motivo'),'ugc');
 assert.equal(post.options.body.get('contexto_pessoa'),'aluna-a');
 assert.equal(post.options.body.get('contexto_site'),'escola-a');
 assert.equal(post.options.body.get('revisao'),'3');
 assert.equal(post.options.headers['X-CSRFToken'],'csrf-teste');
 assert.equal(post.options.credentials,'same-origin');
 assert.equal(post.options.cache,'no-store');
 assert.deepEqual(ui.redirects,['/conquistas/inicio/objetivo/']);
});

test('plano permite rascunho e compromisso com destinos separados',async()=>{
 for(const [assumir,url] of [['nao','/conquistas/'],['sim','/conquistas/inicio/item/']]){
  const ui=await page('plano');await ui.submit(assumir);
  const post=ui.calls.find(call=>call.options.method==='POST');
  assert.equal(post.options.body.get('assumir'),assumir);
  assert.equal(post.options.body.get('sonho'),'SONHO PRIVADO');
  assert.deepEqual(ui.redirects,[url]);
 }
});

test('falha ao salvar não apaga rascunho nem navega e consulta posterior preserva edição',async()=>{
 const ui=await page('plano');ui.form.elements.objetivo.value='Minha edição local';await ui.fire(ui.form,'input');
 ui.fail({ok:false,status:400,json:async()=>({detail:'Seu registro mudou em outra aba.'})});await ui.submit('sim');
 assert.deepEqual(ui.redirects,[]);assert.equal(ui.form.elements.objetivo.value,'Minha edição local');
 const saved=record();saved.inicio.objetivo='Versão salva na outra aba';saved.revisao=4;ui.setRecord(saved);
 await ui.fire(ui.byId('recarregar'),'click');
 assert.equal(ui.form.elements.objetivo.value,'Minha edição local');
 assert.match(ui.byId('comparacao').textContent,/Versão salva na outra aba/);
 await ui.submit('sim');assert.equal(ui.calls.at(-1).options.body.get('revisao'),'4');
});

test('item exige arquivo, rejeita tamanho excessivo e permite confirmar arquivo já guardado',async()=>{
 const ui=await page('item');await ui.submit('declaracao');assert.equal(ui.calls.length,1);
 ui.byId('arquivo').files=[{size:21*1024*1024}];await ui.submit('anexo');assert.equal(ui.calls.length,1);
 ui.byId('arquivo').files=[];ui.setRecord(record({anexos:[file()]}));await ui.reopen();
 await ui.submit('declaracao');assert.equal(ui.calls.at(-1).options.body.get('acao'),'declaracao');
 assert.equal(ui.calls.at(-1).options.body.get('passo'),'2');
});

test('pedido de ajuda usa objetivo e dúvida sem incluir sonho, motivo pessoal ou compromisso',async()=>{
 const ui=await page('item',record({anexos:[file()]}));
 await ui.fire(ui.byId('pedir-ajuda'),'click');await ui.fire(ui.byId('copiar'),'click');
 assert.match(ui.copied[0],/Criar um chapéu/);assert.match(ui.copied[0],/Como suavizar/);
 assert.doesNotMatch(ui.copied[0],/SONHO PRIVADO|COMPROMISSO PRIVADO|Motivo reservado|obra.obj/);
 assert.equal(ui.calls.length,1);
});

test('reabrir após requisito invalidado retira mensagem antiga de conquista concluída',async()=>{
 const ui=await page('item',record({etapas:[{ordem:1,alcancada:true},{ordem:2,alcancada:true}],anexos:[file()]}));
 assert.equal(ui.byId('concluir').hidden,true);
 const updated=record({anexos:[file()]});updated.inicio.confirmado_em=null;ui.setRecord(updated);await ui.reopen();
 assert.equal(ui.byId('concluir').hidden,false);
 assert.doesNotMatch(ui.byId('item-estado').textContent,/já faz parte das suas conquistas/);
});

test('sessão encerrada ou outra conta oculta os dados privados que estavam na tela',async()=>{
 for(const changedAccount of [false,true]){
  const ui=await page('plano');
  if(changedAccount)ui.setRecord(record({pessoa_id:'outra-aluna'}));
  else ui.fail({ok:false,status:403,json:async()=>({detail:'Sua sessão expirou.'})});
  await ui.reopen();assert.equal(ui.byId('conteudo').hidden,true);
  assert.match(ui.byId('status').textContent,/conta mudou|sessão expirou/);
 }
});

test('ao renovar a mesma sessão o rascunho é retomado e a comparação privada não fica exposta durante a falha',async()=>{
 const ui=await page('plano');ui.form.elements.sonho.value='Rascunho privado';await ui.fire(ui.form,'input');
 await ui.reopen();assert.ok(ui.byId('comparacao'));
 ui.fail({ok:false,status:403,json:async()=>({detail:'Sua sessão expirou.'})});await ui.reopen();
 assert.equal(ui.byId('conteudo').hidden,true);assert.equal(ui.byId('comparacao'),null);
 await ui.reopen();assert.equal(ui.byId('conteudo').hidden,false);
 assert.equal(ui.form.elements.sonho.value,'Rascunho privado');
});

test('link de envio posiciona o formulário depois de revelar seu conteúdo',async()=>{
 const ui=await page('item',record(),'#inicio-form-item');
 assert.equal(ui.form.scrolledWhileVisible,true);
});
