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
