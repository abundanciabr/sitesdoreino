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
      pratica:'Comece com uma forma simples.',sonhos_opcoes:[{valor:'pc_gamer',nome:'Comprar um PC Gamer'},{valor:'viagens',nome:'Viajar e conhecer novos lugares'}],motivos:[{valor:'ugc',nome:'Itens próprios'}]},
    etapas:[{ordem:1,alcancada:true},{ordem:2,alcancada:false}],avaliacoes:[],anexos:[],...overrides};
}
function file(overrides={}){
  return {id:1,passo:2,nome:'obra.obj',url:'/trilha/inventario/arquivos/1/',
    criado_em:'2026-10-10T12:00:00Z',aprendi:'Minha tentativa',duvida:'Como suavizar a borda?',...overrides};
}

async function page(step,initial=record(),hash='',wizard=false,embedded=false){
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
  const root=add('jornada');root.dataset={api:'/trilha/inventario/api/',conquistas:'/trilha/',envio:'/trilha/inicio/envio/'};
  const summaries=[new Element('small'),new Element('small'),new Element('small')];
  root.querySelector=selector=>summaries[Number(selector.match(/\d/)[0])-1];
  root.querySelectorAll=selector=>nodes.filter(node=>selector.includes('name="compromisso_checks"')?node.name==='compromisso_checks'&&(!selector.includes(':checked')||node.checked):selector==='[data-compromisso-motivos]'?node.dataset.rotulo:selector==='input[name="motivo_sonhos"]:checked'?node.name==='motivo_sonhos'&&node.checked:selector==='a'?node.tagName==='a':['button','input','textarea','select'].includes(node.tagName));
  if(wizard){['motivo-escolha','motivo-reflexao','motivo-contagem','outro-campo','motivo-escolha-titulo','motivo-reflexao-titulo','motivo-depois-1','motivo-depois-2','motivo-anterior','motivo-sonhos','motivo-sonhos-titulo','motivo-depois-3','sonhos-anterior','sonhos-opcoes'].forEach(id=>add(id));root.querySelector=()=>nodes.find(n=>n.name==='motivo'&&n.value==='outro'&&n.checked)||null;}
  const form=add('form-'+step,'form');form.elements={};
  const fields=step==='motivo'?['motivo_pessoal',...(wizard?['motivo_outro']:[])]:step==='plano'?['sonho','objetivo','quando','obstaculo','plano_b','compromisso','apoio']:step==='criacao'?['item_nome','item_acao']:step==='compromisso'?[]:['arquivo','aprendi','duvida'];
  fields.forEach(name=>{const node=add(name,name==='arquivo'?'input':'textarea');node.name=name;form.elements[name]=node;form.append(node);});
  form.reset=()=>Object.values(form.elements).forEach(node=>{node.value='';node.files=[];});
  ['status','conteudo','recarregar','comparacao'].filter(id=>id!=='comparacao').forEach(id=>add(id,id==='recarregar'?'button':'div'));
  if(step==='motivo'){const options=add('opcoes');form.append(options);}
  if(step==='plano'){add('confirmacao');add('sugestao','button');}
  if(step==='compromisso'){
    for(const value of ['curso','aulas','desafios','motivo']){const check=add('check-'+value,'input');check.name='compromisso_checks';check.type='checkbox';check.value=value;form.append(check);}
    ['compromisso-1','compromisso-2','compromisso-3','compromisso-progresso','compromisso-titulo-1','compromisso-titulo-2','compromisso-titulo-3','compromisso-xp','compromisso-voltar','compromisso-anterior','compromisso-concluido','compromisso-reler'].forEach(id=>add(id));
    for(let i=1;i<=3;i++){const card=add('motivos-'+i);card.dataset.rotulo='Meu motivo';}
  }
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
  const calls=[],redirects=[],copied=[],panelEvents=[],windowEvents={};
  let current=initial,nextError=null;
  const context=vm.createContext({FormData,AbortController,location:{hash},
    document:{getElementById:id=>nodes.find(node=>node.id===id&&!node.removed)||null,createElement:tag=>new Element(tag),createTextNode:text=>{const node=new Element('#text');node.textContent=text;return node;}},
    window:{__testHost:embedded?{close:()=>panelEvents.push('fechado'),navigate:dest=>panelEvents.push(dest)}:{},location:{assign:dest=>redirects.push(dest)},addEventListener:(type,handler)=>{windowEvents[type]=handler;}},
    navigator:{clipboard:{writeText:async text=>copied.push(text)}},
    fetch:async(url,options)=>{calls.push({url,options});if(nextError){const error=nextError;nextError=null;if(error instanceof Error)throw error;return error;}const result=structuredClone(current);if(options.method==='POST'&&!Object.hasOwn(result,'conquista_url'))result.conquista_url='/trilha/inicio/conquista/'+({motivo:1,plano:2,criacao:3,item:4}[step])+'/?comprovante=teste';return {ok:true,status:200,json:async()=>result};}
  });
  vm.runInContext(source.replace('window.iniciarJornada();','window.testController = window.iniciarJornada(document, window.__testHost);'),context);await tick();
  const fire=async(node,type,values={})=>{for(const handler of node.events[type]||[])await handler({preventDefault(){},...values});await tick();};
  return {checkboxes:()=>nodes.filter(node=>node.type==='checkbox'),byId,form,calls,redirects,copied,summaries,fire,panelEvents,close:()=>context.window.testController.close(),
    setRecord:value=>{current=value;},fail:value=>{nextError=value;},
    reopen:async()=>{windowEvents.pageshow({persisted:true});await tick();},
    submit:async value=>fire(form,'submit',{submitter:{value}}),
  };
}

test('checks retomam, salvam ao fechar e falha de salvamento mantém painel e marcações',async()=>{
 const initial=record();initial.inicio.compromisso_etapa=2;initial.inicio.compromisso_checks=['curso','desafios'];
 const ui=await page('compromisso',initial,'',false,true);
 assert.deepEqual(ui.checkboxes().filter(n=>n.checked).map(n=>n.value),['curso','desafios']);
 ui.byId('check-aulas').checked=true;await ui.fire(ui.form,'input');
 ui.fail({ok:false,status:400,json:async()=>({detail:'Seu registro mudou em outra aba.'})});
 await ui.close();assert.deepEqual(ui.panelEvents,[]);assert.equal(ui.byId('check-aulas').checked,true);
 await ui.fire(ui.byId('recarregar'),'click');assert.equal(ui.byId('check-aulas').checked,true);
 await ui.close();assert.deepEqual(ui.panelEvents,['fechado']);
 assert.equal(ui.calls.at(-1).options.body.get('compromisso_checks'),'["curso","aulas","desafios"]');
 assert.equal(ui.calls.at(-1).options.body.get('compromisso_etapa'),'2');
 assert.equal(ui.calls.at(-1).options.body.get('assumir'),undefined);
});

test('compromisso mostra motivo e sonhos, assume explicitamente e confirma sem trocar de página',async()=>{
 const initial=record(); initial.inicio.motivo_sonhos=['pc_gamer'];
 const ui=await page('compromisso',initial,'',false,true);
 assert.equal(ui.byId('compromisso-1').hidden,false);
 assert.match(ui.byId('motivos-1').textContent,/Itens próprios/);
 assert.match(ui.byId('motivos-1').textContent,/Motivo reservado/);
 assert.match(ui.byId('motivos-1').textContent,/Comprar um PC Gamer/);
 assert.doesNotMatch(ui.byId('motivos-1').textContent,/SONHO PRIVADO|COMPROMISSO PRIVADO/);
 await ui.submit('continuar');
 assert.equal(ui.calls.at(-1).options.body.get('acao'),'inicio-compromisso');
 assert.equal(ui.calls.at(-1).options.body.get('compromisso_etapa'),'2');
 assert.equal(ui.calls.at(-1).options.body.get('assumir'),undefined);
 assert.equal(ui.byId('compromisso-2').hidden,false);
 const saved=record();saved.inicio.compromisso_curso_em='2026-10-11T12:00:00Z';saved.inicio.etapas=[{}, {concluida:true}];saved.conquista_xp=100;ui.setRecord(saved);
 await ui.submit('assumir');
 assert.equal(ui.calls.at(-1).options.body.get('assumir'),'sim');
 assert.equal(ui.calls.at(-1).options.body.get('proximo_passo'),undefined);
 assert.equal(ui.calls.at(-1).options.body.get('objetivo'),undefined);
 assert.equal(ui.byId('compromisso-3').hidden,false);
 assert.match(ui.byId('compromisso-xp').textContent,/100 XP/);
 assert.deepEqual(ui.redirects,[]);assert.deepEqual(ui.panelEvents,[]);
 await ui.close();assert.deepEqual(ui.panelEvents,['fechado']);
});

test('compromisso retoma a declaração e falha mantém decisão sem confirmação fictícia',async()=>{
 const saved=record();saved.inicio.compromisso_curso_em='2026-10-11T12:00:00Z';
 const ui=await page('compromisso',saved,'',false,true);
 assert.equal(ui.byId('compromisso-2').hidden,false);
 ui.fail({ok:false,status:400,json:async()=>({detail:'Seu registro mudou em outra aba.'})});
 await ui.submit('assumir');
 assert.equal(ui.byId('compromisso-3').hidden,true);
 assert.match(ui.byId('status').textContent,/outra aba/);
 assert.deepEqual(ui.panelEvents,[]);
});

test('compromisso assumido reabre a confirmação e sair não faz um novo POST',async()=>{
 const saved=record();saved.inicio.compromisso_curso_em='2026-10-11T12:00:00Z';saved.inicio.etapas=[{}, {concluida:true}];
 const ui=await page('compromisso',saved,'',false,true);
 assert.equal(ui.byId('compromisso-3').hidden,false);
 assert.equal(ui.byId('compromisso-xp').hidden,true);
 await ui.fire(ui.byId('compromisso-reler'),'click');
 assert.equal(ui.byId('compromisso-1').hidden,false);
 await ui.close();assert.equal(ui.calls.length,1);assert.deepEqual(ui.panelEvents,['fechado']);
});

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
 assert.deepEqual(ui.redirects,['/trilha/inicio/conquista/1/?comprovante=teste']);
});

test('salvar motivo como rascunho não abre celebração nem a próxima tarefa',async()=>{
 const ui=await page('motivo');await ui.submit('pausar');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
 assert.deepEqual(ui.redirects,['/trilha/']);
});

test('plano permite rascunho e compromisso com destinos separados',async()=>{
 for(const [assumir,url] of [['nao','/trilha/'],['sim','/trilha/inicio/conquista/2/?comprovante=teste']]){
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
 assert.deepEqual(ui.redirects,['/trilha/inicio/conquista/4/?comprovante=teste']);
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
 assert.equal(ui.byId('enviar').textContent,'Avaliar esta versão ou uma nova');
 const updated=record({anexos:[file()]});updated.inicio.confirmado_em=null;ui.setRecord(updated);await ui.reopen();
 assert.equal(ui.byId('enviar').textContent,'Avaliar esta versão ou uma nova');
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
 assert.deepEqual(ui.redirects,['/trilha/inicio/conquista/3/?comprovante=teste']);
});

test('link antigo para envio encaminha para a quarta tela somente quando a criação está pronta',async()=>{
 for(const pronta of [false,true]){
  const dados=record();dados.inicio.item_pronto=pronta;
  const ui=await page('criacao',dados,'#inicio-form-item');
  assert.deepEqual(ui.redirects,pronta?['/trilha/inicio/envio/']:[]);
 }
});

test('a tela de envio não contém os controles nem o pedido de ajuda das etapas anteriores',async()=>{
 const ui=await page('item',record({anexos:[file()]}));
 assert.equal(ui.byId('objetivo-salvo'),null);
 assert.equal(ui.byId('pedir-ajuda'),null);
 assert.equal(ui.byId('form-criacao'),null);
 assert.equal(ui.byId('historico').hidden,false);
});

test('três etapas guardam a escolha sem XP e permitem concluir a reflexão vazia',async()=>{
 const initial=record();initial.inicio.motivo_pessoal='';
 const ui=await page('motivo',initial,'',true);
 assert.equal(ui.byId('motivo-escolha').hidden,false);assert.equal(ui.byId('motivo-reflexao').hidden,true);
 await ui.submit('proxima');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_etapa'),'2');
 assert.equal(ui.byId('motivo-escolha').hidden,true);assert.equal(ui.byId('motivo-reflexao').hidden,false);
 assert.deepEqual(ui.redirects,[]);
 await ui.submit('proxima');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_etapa'),'3');
 assert.equal(ui.byId('motivo-reflexao').hidden,true);assert.equal(ui.byId('motivo-sonhos').hidden,false);
 assert.deepEqual(ui.redirects,[]);
 await ui.submit('continuar');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'sim');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_pessoal'),'');
 assert.match(ui.redirects[0],/conquista/);
});
test('outro motivo, retomada e depois preservam rascunho na etapa correta',async()=>{
 const initial=record();Object.assign(initial.inicio,{motivo:'outro',motivo_outro:'Criar cenários',motivo_etapa:2,motivos:[{valor:'outro',nome:'Tenho outro motivo'}]});
 const ui=await page('motivo',initial,'',true);
 assert.equal(ui.byId('outro-campo').hidden,false);assert.equal(ui.form.elements.motivo_outro.value,'Criar cenários');
 assert.equal(ui.byId('motivo-reflexao').hidden,false);
 await ui.fire(ui.byId('motivo-anterior'),'click');
 assert.equal(ui.byId('motivo-escolha').hidden,false);assert.equal(ui.byId('motivo-reflexao').hidden,true);
 ui.form.elements.motivo_outro.value='Criar miniaturas';await ui.fire(ui.form,'input');
 ui.fail(new Error('Sem conexão'));await ui.fire(ui.byId('motivo-depois-1'),'click');
 assert.deepEqual(ui.redirects,[]);assert.equal(ui.form.elements.motivo_outro.value,'Criar miniaturas');
 await ui.fire(ui.byId('motivo-depois-1'),'click');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_outro'),'Criar miniaturas');
 assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_etapa'),'1');
 assert.deepEqual(ui.redirects,['/trilha/']);
});

test('painel direto conclui e fecha sem trocar a pagina da trilha',async()=>{
 const ui=await page('motivo',record(),'',true,true);
 await ui.submit('proxima');await ui.submit('proxima');await ui.submit('continuar');
 assert.deepEqual(ui.redirects,[]);
 assert.deepEqual(ui.panelEvents,['/trilha/inicio/conquista/1/?comprovante=teste&embutido=1']);
 const draft=await page('motivo',record(),'',true,true);
 draft.form.elements.motivo_pessoal.value='Minha reflexão';await draft.fire(draft.form,'input');
 await draft.close();assert.deepEqual(draft.redirects,[]);assert.deepEqual(draft.panelEvents,['fechado']);
 assert.equal(draft.calls.at(-1).options.body.get('motivo_pessoal'),'Minha reflexão');
 assert.equal(draft.calls.at(-1).options.body.get('concluir'),'nao');
});


test('voltar aparece nas três etapas somente depois do XP recebido e preserva a revisão',async()=>{
 for(const xp of [0,100]) for(const etapa of [1,2,3]) {
  const initial=record();initial.inicio.motivo_etapa=etapa;
  initial.inicio.etapas=[{etapa:1,xp_recebido:xp,concluida:xp>0}];
  const ui=await page('motivo',initial,'',true,true);
  if(xp) for(let n=1;n<etapa;n++) await ui.submit('proxima');
  const label=xp?'← Voltar':'← Depois eu faço isso';
  for(const n of [1,2,3]) assert.equal(ui.byId('motivo-depois-'+n).textContent,label);
  ui.form.elements.motivo_pessoal.value='Motivo revisto';await ui.fire(ui.form,'input');
  assert.match(ui.byId('status').textContent,xp?/Voltar/:/Depois eu faço isso/);
  await ui.fire(ui.byId('motivo-depois-'+etapa),'click');
  assert.equal(ui.calls.at(-1).options.body.get('motivo_pessoal'),'Motivo revisto');
  assert.equal(ui.calls.at(-1).options.body.get('concluir'),'nao');
  assert.deepEqual(ui.panelEvents,['fechado']);
 }
});


test('concluir revisão salva e retorna à trilha; primeira conclusão mantém a celebração',async()=>{
 for(const embedded of [false,true]) for(const jaRecebida of [false,true]) {
  const initial=record();initial.inicio.motivo_etapa=2;
  initial.inicio.etapas=[{etapa:1,xp_recebido:jaRecebida?100:0,concluida:jaRecebida}];
  const ui=await page('motivo',initial,'',true,embedded);
  if(jaRecebida) await ui.submit('proxima');
  await ui.submit('proxima');
  ui.form.elements.motivo_pessoal.value='Minha reflexão atualizada';await ui.fire(ui.form,'input');
  ui.fail(new Error('Sem conexão'));await ui.submit('continuar');
  assert.deepEqual(ui.redirects,[]);assert.deepEqual(ui.panelEvents,[]);
  assert.equal(ui.form.elements.motivo_pessoal.value,'Minha reflexão atualizada');
  ui.setRecord({...initial,conquista_ja_recebida:jaRecebida,conquista_xp:jaRecebida?0:100});
  await ui.submit('continuar');
  assert.equal(ui.calls.at(-1).options.body.get('concluir'),'sim');
  assert.equal(ui.calls.at(-1).options.body.get('motivo_pessoal'),'Minha reflexão atualizada');
  const receipt='/trilha/inicio/conquista/1/?comprovante=teste';
  assert.deepEqual(ui.redirects,embedded?[]:[jaRecebida?'/trilha/':receipt]);
  assert.deepEqual(ui.panelEvents,embedded?[jaRecebida?'fechado':receipt+'&embutido=1']:[]);
 }
});


test('revisar sempre abre a escolha; rascunho continua retomando a segunda etapa',async()=>{
 for(const embedded of [false,true]) for(const concluido of [false,true]) {
  const initial=record();Object.assign(initial.inicio,{motivo_etapa:2,motivo_outro:'Texto preservado',etapas:[{etapa:1,xp_recebido:concluido?100:0,concluida:concluido}]});
  const ui=await page('motivo',initial,'',true,embedded);
  assert.equal(ui.byId('motivo-escolha').hidden,!concluido);
  assert.equal(ui.byId('motivo-reflexao').hidden,concluido);
  assert.equal(ui.form.elements.motivo_pessoal.value,'Motivo reservado');
  assert.equal(ui.form.elements.motivo_outro.value,'Texto preservado');
  assert.equal(ui.byId('outro-campo').hidden,false);
  assert.equal(ui.calls.filter(call=>call.options.method==='POST').length,0);
  if(concluido) {
   await ui.submit('proxima');
   assert.equal(ui.byId('motivo-escolha').hidden,true);
   assert.equal(ui.byId('motivo-reflexao').hidden,false);
   assert.equal(ui.calls.at(-1).options.body.get('motivo'),'ugc');
   assert.equal(ui.calls.at(-1).options.body.get('motivo_pessoal'),'Motivo reservado');
  }
  await ui.reopen();
  assert.equal(ui.byId('motivo-escolha').hidden,!concluido);
  assert.equal(ui.byId('motivo-reflexao').hidden,concluido);
  assert.deepEqual(ui.redirects,[]);assert.deepEqual(ui.panelEvents,[]);
 }
});


test('sonhos permitem várias escolhas, desmarcação, retomada e saída segura na terceira etapa',async()=>{
 const initial=record();Object.assign(initial.inicio,{motivo_etapa:3,motivo_sonhos:['pc_gamer']});
 const ui=await page('motivo',initial,'',true,true);
 assert.equal(ui.byId('motivo-escolha').hidden,true);assert.equal(ui.byId('motivo-reflexao').hidden,true);assert.equal(ui.byId('motivo-sonhos').hidden,false);
 assert.equal(ui.byId('motivo-contagem').textContent,'Etapa 3 de 3');
 assert.deepEqual(ui.checkboxes().map(check=>check.checked),[true,false]);
 ui.checkboxes()[1].checked=true;await ui.fire(ui.form,'input');
 ui.fail(new Error('Sem conexão'));await ui.close();
 assert.deepEqual(ui.panelEvents,[]);assert.deepEqual(ui.checkboxes().map(check=>check.checked),[true,true]);
 await ui.fire(ui.byId('sonhos-anterior'),'click');
 assert.equal(ui.byId('motivo-reflexao').hidden,false);assert.equal(ui.byId('motivo-sonhos').hidden,true);
 await ui.submit('proxima');
 assert.deepEqual(JSON.parse(ui.calls.at(-1).options.body.get('motivo_sonhos')),['pc_gamer','viagens']);
 ui.checkboxes().forEach(check=>{check.checked=false;});await ui.fire(ui.form,'input');
 await ui.close();assert.deepEqual(ui.panelEvents,['fechado']);
 assert.equal(ui.calls.at(-1).options.body.get('motivo_sonhos'),'[]');
 assert.equal(ui.calls.at(-1).options.body.get('motivo_etapa'),'3');
 initial.inicio.etapas=[{etapa:1,xp_recebido:100,concluida:true}];
 const review=await page('motivo',initial,'',true,true);
 assert.equal(review.byId('motivo-escolha').hidden,false);assert.equal(review.byId('motivo-sonhos').hidden,true);
 assert.deepEqual(review.checkboxes().map(check=>check.checked),[true,false]);
});

test('resultado atual incompleto prevalece sobre avaliação histórica e não celebra',async()=>{
 const atual=record({conquista_url:null,
   avaliacoes:[{ordem:3,resultado:'reconhecida',feedback:'Uma versão antiga foi aceita.'}],
   avaliacao_atual:{ordem:3,resultado:'incompleta',feedback:'Descreva a ação feita nesta versão.',conquistada:false}});
 const ui=await page('criacao',atual);
 ui.form.elements.item_nome.value='Boné';ui.form.elements.item_acao.value='';
 await ui.submit();
 assert.equal(ui.calls.at(-1).options.body.get('acao'),'inicio-item');
 assert.deepEqual(ui.redirects,[]);
 assert.match(ui.byId('status').textContent,/Descreva a ação feita nesta versão/);
 assert.doesNotMatch(ui.byId('status').textContent,/versão antiga/);
});

test('retorno obsoleto durante análise não abre comprovante de outra versão',async()=>{
 const atual=record({conquista_url:null,
   avaliacoes:[{ordem:4,resultado:'reconhecida',feedback:'A versão anterior foi aceita.'}],
   avaliacao_atual:{ordem:4,resultado:'falha',feedback:'Seu caminho mudou durante a análise. Tente novamente.',conquistada:false}});
 const ui=await page('item',atual);
 ui.byId('arquivo').files=[{size:300,name:'nova.obj'}];
 await ui.submit();
 assert.deepEqual(ui.redirects,[]);
 assert.match(ui.byId('status').textContent,/caminho mudou/);
 assert.equal(ui.calls.at(-1).options.body.get('acao'),'inicio-envio');
});
