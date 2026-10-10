const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../apps/core/trilha_v4_assets/app.js'), 'utf8');
const bootstrap = {aluno:{nome:'Ana'},pessoa_id:'aluna-a',site_id:'mesh'};
function progress(){return {pessoa_id:'aluna-a',site_id:'mesh',atual_ordem:3,total_cents:0,meta_cents:null,meta_escolhida:false,
  etapas:Array.from({length:13},(_,i)=>({ordem:i+1,alcancada:i===0||i===2,conquista:'Registrada',meta_cents:null,alcancada_em:null}))};}
async function load(response){
  const nodes = new Map();
  const result = {};
  const context = vm.createContext({
    document:{querySelector(selector){
      if(!nodes.has(selector))nodes.set(selector,{textContent:selector==='#trilha-data'?JSON.stringify(bootstrap):'',removeAttribute(){},setAttribute(){}});
      return nodes.get(selector);
    }},
    window:{location:{replace(url){result.redirect=url;}}},
    fetch:async(url, options)=>{result.request={url,options};if(response instanceof Error)throw response;return response;},
  });
  vm.runInContext(source,context);
  context.renderJourney=payload=>{result.payload=JSON.parse(JSON.stringify(payload));};
  await new Promise(resolve=>setImmediate(resolve));
  result.nodes=nodes;
  return result;
}

test('carrega a jornada propria sem depender da ponte de rede do funil',async()=>{
  const data=progress();
  const r=await load({ok:true,status:200,json:async()=>data});
  assert.deepEqual(r.payload.progresso,data);
  assert.equal(r.request.url,'/conquistas/minha-trilha/');
  assert.equal(r.request.options.credentials,'same-origin');
  assert.equal(r.request.options.cache,'no-store');
  assert.equal(r.redirect,undefined);
});

test('sessao encerrada volta ao login sem desenhar dados',async()=>{
  const r=await load({ok:false,status:403});
  assert.equal(r.redirect,'/login?next=%2Ftrilha%2F');
  assert.equal(r.payload,undefined);
});

test('nao desenha resposta de outra pessoa ou escola nem faixas inconsistentes',async()=>{
  for(const mutate of [d=>d.pessoa_id='aluna-b',d=>d.site_id='outra-escola',d=>d.atual_ordem=13,d=>d.etapas.pop(),d=>d.meta_escolhida=true]){
    const data=progress();mutate(data);
    const r=await load({ok:true,status:200,json:async()=>data});
    assert.equal(r.payload,undefined);
    assert.equal(r.nodes.get('.object-caption').textContent,'PROGRESSO INDISPONÍVEL');
  }
});

test('falhas da rede e do servidor nao viram progresso ficticio',async()=>{
  for(const response of [{ok:false,status:503},new Error('offline'),{ok:true,status:200,json:async()=>{throw new Error('invalid json');}}]){
    const r=await load(response);
    assert.equal(r.payload,undefined);
    assert.equal(r.nodes.get('.object-caption').textContent,'PROGRESSO INDISPONÍVEL');
  }
});
