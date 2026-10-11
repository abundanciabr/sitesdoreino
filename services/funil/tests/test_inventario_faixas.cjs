const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../apps/core/trilha_v4_assets/inventario.js'),'utf8');
const sandbox={};vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('function inventoryStepsFor('),source.indexOf('function renderBelts(')),sandbox);
function stage(current,selected,reached,total=13){
 const data={atual_ordem:current,etapas:Array.from({length:total},(_,i)=>({ordem:i+1,alcancada:reached?reached.includes(i+1):i<current}))};
 return Array.from(sandbox.inventoryStepsFor(data,selected));
}
test('branca mostra somente o passo da amarela',()=>assert.deepEqual(stage(1,1),[1,2]));
test('amarela abre o relato do item, sem pular para Sandbox',()=>assert.deepEqual(stage(2,2),[2,3]));
test('azul abre o envio avaliado, sem pular para a Fila',()=>assert.deepEqual(stage(3,3),[3,4]));
test('vermelha abre a prática do caminho',()=>assert.deepEqual(stage(4,4),[4,5]));
test('freelancer vê Sandbox na quinta e Fila na sexta',()=>assert.deepEqual(stage(5,5),[5,6]));
test('caminho curto encerra na preta sem inventar graus',()=>assert.deepEqual(stage(7,7,undefined,7),[7]));
test('faixas bloqueadas nunca revelam requisitos nem pelo número',()=>{
 for(let current=1;current<13;current++)for(let target=current+1;target<=13;target++)assert.deepEqual(stage(current,target),[]);
 assert.deepEqual(stage(3,2,[1,3]),[]);
});
test('faixas anteriores mostram apenas seu próprio registro',()=>{
 for(let current=2;current<=13;current++)for(let target=1;target<current;target++)assert.deepEqual(stage(current,target),[target]);
});
test('último grau não inventa uma etapa seguinte',()=>assert.deepEqual(stage(13,13),[13]));

test('inventario usa os creditos e bloqueios do servidor para liberar a proxima tarefa',()=>{
 for(let done=0;done<=4;done++){
  const etapas=Array.from({length:4},(_,i)=>({etapa:i+1,concluida:i<done,liberada:i<=done,bloqueada:i>done}));
  const states=Array.from(sandbox.inventoryStartSteps({etapas}));
  assert.equal(states.filter(s=>s.done).length,done);
  assert.deepEqual(states.map(s=>s.id),['motivo','plano','item','envio']);
  assert.deepEqual(states.map(s=>s.url),['/trilha/inicio/motivo/','/trilha/inicio/objetivo/','/trilha/inicio/item/','/trilha/inicio/envio/']);
  assert.deepEqual(states.map(s=>s.blocked),[0,1,2,3].map(i=>i>done));
 }
});
test('inventario sem estados novos fecha acesso e nao presume conclusao pelos campos antigos',()=>{
 assert.ok(Array.from(sandbox.inventoryStartSteps({motivo:'ugc',objetivo:'teste',compromisso:'teste',item_pronto:true})).every(s=>s.blocked));
 const etapas=[1,2,3,4].map(etapa=>({etapa,liberada:true,bloqueada:false,concluida:etapa!==1}));
 assert.deepEqual(Array.from(sandbox.inventoryStartSteps({etapas}),s=>s.blocked),[false,true,true,true]);
});

test('reinício na branca mantém arquivos de etapas superiores acessíveis no histórico privado',()=>{
 const nodes=new Map();
 const element=(tag,text='')=>({tag,textContent:text,children:[],parentElement:{dataset:{},setAttribute(){},removeAttribute(){}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(){},removeAttribute(){}});
 const q=selector=>{if(!nodes.has(selector))nodes.set(selector,element('div'));return nodes.get(selector);};
 const data={caminho:'ugc',graus_historicos:[{ordem:7,bonus_xp:50,conquistada_em:'2026-10-11T12:00:00Z'}],
  atual_ordem:1,inicio:{},meta_cents:null,proposito:'',total:'0,00',recebimentos:[],historico:[],
  etapas:Array.from({length:7},(_,i)=>({ordem:i+1,nome:String(i+1),alcancada:i===0})),
  anexos:[{passo:3,nome:'pratica.blend',url:'/trilha/inventario/arquivos/23/'},{passo:4,nome:'entrega.glb',url:'/trilha/inventario/arquivos/24/'},{passo:4,nome:'externo',url:'https://example.test/'}]};
 const ctx={data,q,el:element,document:{createElement:tag=>element(tag)},location:{hash:''},selectedOrder:null,previousCurrent:null,fileList(){},renderBelts(){},inventoryStepsFor:()=>[1,2],inventoryStartSteps:sandbox.inventoryStartSteps};
 vm.createContext(ctx);
 vm.runInContext(source.slice(source.indexOf('function render(){'),source.indexOf('function inventoryStepsFor(')),ctx);
 ctx.render();
 const links=nodes.get('#history').children.flatMap(node=>node.children.filter(child=>child.tag==='a'));
 assert.deepEqual(links.map(link=>link.textContent),['pratica.blend','entrega.glb']);
 assert.deepEqual(links.map(link=>link.href),['/trilha/inventario/arquivos/23/','/trilha/inventario/arquivos/24/']);
 assert.match(nodes.get('#history').children.flatMap(node=>node.children).map(node=>node.textContent).join(' '),/Grau I · \+50 XP/);
 assert.equal(nodes.get('#deliveries').children.length,0);
});

test('inventário mostra Sandbox e Fila só nas etapas cinco e seis do freelancer',()=>{
 const render=(caminho,total)=>{
  const nodes=new Map();
  const element=(tag,text='')=>({tag,textContent:text,children:[],parentElement:{dataset:{},setAttribute(){},removeAttribute(){}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];},setAttribute(){},removeAttribute(){}});
  const q=selector=>{if(!nodes.has(selector))nodes.set(selector,element('div'));return nodes.get(selector);};
  const data={caminho,graus_historicos:[],atual_ordem:5,inicio:{etapas:[]},meta_cents:null,proposito:'',total:'R$ 0,00',recebimentos:[],historico:[],anexos:[],
    etapas:Array.from({length:total},(_,i)=>({ordem:i+1,nome:String(i+1),conquista:'Atividade avaliada',alcancada:i<5}))};
  const ctx={data,q,el:element,document:{createElement:tag=>element(tag)},location:{hash:''},selectedOrder:5,previousCurrent:null,fileList(){},renderBelts(){},inventoryStepsFor:sandbox.inventoryStepsFor,inventoryStartSteps:sandbox.inventoryStartSteps};
  vm.createContext(ctx);
  vm.runInContext(source.slice(source.indexOf('function render(){'),source.indexOf('function inventoryStepsFor(')),ctx);
  ctx.render();
  return nodes.get('#deliveries').children;
 };
 const freelancer=render('freelancer',13);
 assert.deepEqual(freelancer.map(item=>item.children.find(child=>child.tag==='summary')?.textContent),[
  'Minha prática no Sandbox · Concluído','Meu trabalho real na Fila · Pendente']);
 assert.deepEqual(freelancer.map(item=>item.children.find(child=>child.tag==='a')?.href),['/trilha/sandbox/','/trilha/fila/']);
 for(const caminho of ['ugc','jogo','aprender']){
  const atividades=render(caminho,7);
  assert.equal(atividades.length,1);
  assert.match(atividades[0].children.find(child=>child.tag==='summary').textContent,/Prática da faixa/);
  assert.equal(atividades[0].children.find(child=>child.tag==='a').href,'/trilha/ciclo/');
  assert.ok(!atividades[0].children.some(child=>/Sandbox|Fila/.test(child.textContent)));
 }
});
