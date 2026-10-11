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
  const root=add('jornada');root.dataset={api:'/conquistas/inventario/',conquistas:'/conquistas/',envio:'/conquistas/inicio/envio/'};
  const summaries=[new Element('small'),new Element('small'),new Element('small')];
  root.querySelector=selector=>summaries[Number(selector.match(/\d/)[0])-1];
  root.querySelectorAll=selector=>nodes.filter(node=>selector==='a'?node.tagName==='a':['button','input','textarea','select'].includes(node.tagName));
  const form=add('form-'+step,'form');form.elements={};
  const fields=step==='motivo'?['motivo_pessoal']:step==='plano'?['sonho','objetivo','quando','obstaculo','plano_b','compromisso','apoio']:step==='criacao'?[]:['arquivo','aprendi','duvida'];
  fields.forEach(name=>{const node=add(name,name==='arquivo'?'input':'textarea');node.name=name;form.elements[name]=node;form.append(node);});
  form.reset=()=>Object.values(form.elements).forEach(node=>{node.value='';node.files=[];});
  ['status','conteudo','recarregar','comparacao'].filter(id=>id!=='comparacao').forEach(id=>add(id,id==='recarregar'?'button':'div'));
  if(step==='motivo'){const options=add('opcoes');form.append(options);}
  if(step==='plano'){add('confirmacao');add('sugestao','button');}
  if(step==='criacao')['objetivo-salvo','pratica','apoio-texto','criacao-estado','pedir-ajuda','ajuda','mensagem','copiar'].forEach(id=>add(id));
  if(step==='item')['enviar','item-estado','historico','versoes'].forEach(id=>add(id));
  const byId=id=>nodes.find(node=>node.id==='inicio-'+id&&!node.removed)||null;
  byId('conteudo').hidden=true;
  if(step==='criacao')byId('ajuda').hidden=true;
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
    fetch:async(url,options)=>{calls.push({url,options});if(nextError){const error=nextError;nextError=null;if(error instanceof Error)throw error;return error;}const result=structuredClone(current);if(options.method==='POST')result.conquista_url='/conquistas/inicio/conquista/'+({motivo:1,plano:2,criacao:3,item:4}[step])+'/?comprovante=teste';return {ok:true,status:200,json:async()=>result};}
  });
  vm.runInContext(source,context);await tick();
  const fire=async(node,type,values={})=>{for(const handler of node.events[type]||[])await handler({preventDefault(){},...values});await tick();};
  return {byId,form,calls,redirects,copied,summaries,fire,
    setRecord:value=>{current=value;},fail:value=>{nextError=value;},
    reopen:async()=>{windowEvents.pageshow({persisted:true});await tick();},
    submit:async value=>fire(form,'submit',{submitter:{value}}),
  };
}

test('motivo salvo é retomado e concluir leva à recompensa depois de salvar com identidade, revisão e CSRF',async()=>{
 const ui=await page('motivo');
 assert.equal(ui.form.elements.motivo_pessoal.value,'Motivo reservado');
 assert.equal(ui.byId('conteudo').hidden,false);
 await ui.submit('continuar');
 const post=ui.calls.find(call=>call.options.method==='POST');
 assert.equal(post.options.body.get('acao'),'inicio-motivo');
 assert.equal(post.options.body.get('motivo'),'ugc');
 assert.equal(post.options.body.get('concluir'),'sim');
 assert.equal(post.options.body.get('contexto_pessoa'),'aluna-a');
 assert.equal(post.options.body.get('contexto_site'),'escola-a');
 assert.equal(post.options.body.get('revisao'),'3');
 assert.equal(post.options.headers['X-CSRFToken'],'csrf-teste');
 assert.equal(post.options.credentials,'same-origin');
 assert.equal(post.options.cache,'no-store');
 assert.deepEqual(ui.redirects,['/conquistas/inicio/conquista/1/?comprovante=teste']);
});

test('salvar motivo como rascunho não abre celebração nem a próxima tarefa',async()=>{
 const ui=await page('motivo');await ui.submit('pausar');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
 assert.deepEqual(ui.redirects,['/conquistas/']);
});

test('plano permite rascunho e compromisso com destinos separados',async()=>{
 for(const [assumir,url] of [['nao','/conquistas/'],['sim','/conquistas/inicio/conquista/2/?comprovante=teste']]){
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

test('envio exige arquivo, rejeita tamanho excessivo e permite confirmar arquivo já guardado',async()=>{
 const ui=await page('item');await ui.submit();assert.equal(ui.calls.length,1);
 ui.byId('arquivo').files=[{size:21*1024*1024}];await ui.submit();assert.equal(ui.calls.length,1);
 ui.byId('arquivo').files=[];ui.setRecord(record({anexos:[file()]}));await ui.reopen();
 await ui.submit();assert.equal(ui.calls.at(-1).options.body.get('acao'),'inicio-envio');
 assert.equal(ui.calls.at(-1).options.body.get('passo'),'2');
 assert.equal(ui.calls.at(-1).options.body.get('sonho'),undefined);
 assert.deepEqual(ui.redirects,['/conquistas/inicio/conquista/4/?comprovante=teste']);
});

test('pedido de ajuda usa objetivo e dúvida sem incluir sonho, motivo pessoal ou compromisso',async()=>{
 const ui=await page('criacao',record({anexos:[file()]}));
 await ui.fire(ui.byId('pedir-ajuda'),'click');await ui.fire(ui.byId('copiar'),'click');
 assert.match(ui.copied[0],/Criar um chapéu/);assert.match(ui.copied[0],/Como suavizar/);
 assert.doesNotMatch(ui.copied[0],/SONHO PRIVADO|COMPROMISSO PRIVADO|Motivo reservado|obra.obj/);
 assert.equal(ui.calls.length,1);
});

test('reabrir após requisito invalidado retira mensagem antiga de conquista concluída',async()=>{
 const ui=await page('item',record({etapas:[{ordem:1,alcancada:true},{ordem:2,alcancada:true}],anexos:[file()]}));
 assert.equal(ui.byId('enviar').textContent,'Enviar uma nova versão');
 const updated=record({anexos:[file()]});updated.inicio.confirmado_em=null;ui.setRecord(updated);await ui.reopen();
 assert.equal(ui.byId('enviar').textContent,'Confirmar meu envio e concluir');
 assert.doesNotMatch(ui.byId('item-estado').textContent,/Envio concluído/);
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

test('criação é confirmada sem upload e abre sua recompensa, sem pular para a próxima tarefa',async()=>{
 const ui=await page('criacao');
 assert.equal(ui.byId('arquivo'),null);
 assert.equal(ui.byId('form-plano'),null);
 await ui.submit();
 assert.equal(ui.calls.at(-1).options.body.get('acao'),'inicio-item');
 assert.equal(ui.calls.at(-1).options.body.get('arquivo'),undefined);
 assert.deepEqual(ui.redirects,['/conquistas/inicio/conquista/3/?comprovante=teste']);
});

test('link antigo para envio encaminha para a quarta tela somente quando a criação está pronta',async()=>{
 for(const pronta of [false,true]){
  const dados=record();dados.inicio.item_pronto=pronta;
  const ui=await page('criacao',dados,'#inicio-form-item');
  assert.deepEqual(ui.redirects,pronta?['/conquistas/inicio/envio/']:[]);
 }
});

test('a tela de envio não contém os controles nem o pedido de ajuda das etapas anteriores',async()=>{
 const ui=await page('item',record({anexos:[file()]}));
 assert.equal(ui.byId('objetivo-salvo'),null);
 assert.equal(ui.byId('pedir-ajuda'),null);
 assert.equal(ui.byId('form-criacao'),null);
 assert.equal(ui.byId('historico').hidden,false);
});
