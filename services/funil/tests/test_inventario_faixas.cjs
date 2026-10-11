const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../apps/core/trilha_v4_assets/inventario.js'),'utf8');
const sandbox={};vm.createContext(sandbox);
vm.runInContext(source.slice(source.indexOf('function inventoryStepsFor('),source.indexOf('function renderBelts(')),sandbox);
function stage(current,selected,reached){
 const data={atual_ordem:current,etapas:Array.from({length:13},(_,i)=>({ordem:i+1,alcancada:reached?reached.includes(i+1):i<current}))};
 return Array.from(sandbox.inventoryStepsFor(data,selected));
}
test('branca mostra somente entrada e primeiro item',()=>assert.deepEqual(stage(1,1),[1,2]));
test('amarela abre prática mas não trabalho real nem recebimentos',()=>assert.deepEqual(stage(2,2),[2,3]));
test('azul abre trabalho real mas não recebimentos',()=>assert.deepEqual(stage(3,3),[3,4]));
test('vermelha abre primeiro recebimento mas ainda não a meta',()=>assert.deepEqual(stage(4,4),[4,5]));
test('verde libera meta dos próximos marcos',()=>assert.deepEqual(stage(5,5),[5,6]));
test('faixas bloqueadas nunca revelam requisitos nem pelo número',()=>{
 for(let current=1;current<13;current++)for(let target=current+1;target<=13;target++)assert.deepEqual(stage(current,target),[]);
 assert.deepEqual(stage(3,2,[1,3]),[]);
});
test('faixas anteriores mostram apenas seu próprio registro',()=>{
 for(let current=2;current<=13;current++)for(let target=1;target<current;target++)assert.deepEqual(stage(current,target),[target]);
});
test('último grau não inventa uma etapa seguinte',()=>assert.deepEqual(stage(13,13),[13]));

test('reinício na branca mantém arquivos de etapas superiores acessíveis no histórico privado',()=>{
 const nodes=new Map();
 const element=(tag,text='')=>({tag,textContent:text,children:[],parentElement:{dataset:{}},append(...items){this.children.push(...items);},replaceChildren(){this.children=[];}});
 const q=selector=>{if(!nodes.has(selector))nodes.set(selector,element('div'));return nodes.get(selector);};
 const data={atual_ordem:1,inicio:{},meta_cents:null,proposito:'',total:'0,00',recebimentos:[],historico:[],
  etapas:Array.from({length:13},(_,i)=>({ordem:i+1,nome:String(i+1),alcancada:i===0})),
  anexos:[{passo:3,nome:'pratica.blend',url:'/conquistas/inventario/arquivos/23/'},{passo:4,nome:'entrega.glb',url:'/conquistas/inventario/arquivos/24/'},{passo:4,nome:'externo',url:'https://example.test/'}]};
 const ctx={data,q,el:element,location:{hash:''},selectedOrder:null,previousCurrent:null,fileList(){},renderBelts(){},inventoryStepsFor:()=>[1,2]};
 vm.createContext(ctx);
 vm.runInContext(source.slice(source.indexOf('function render(){'),source.indexOf('function inventoryStepsFor(')),ctx);
 ctx.render();
 const links=nodes.get('#history').children.flatMap(node=>node.children.filter(child=>child.tag==='a'));
 assert.deepEqual(links.map(link=>link.textContent),['pratica.blend','entrega.glb']);
 assert.deepEqual(links.map(link=>link.href),['/conquistas/inventario/arquivos/23/','/conquistas/inventario/arquivos/24/']);
 assert.equal(nodes.get('#deliveries').children.length,0);
});
