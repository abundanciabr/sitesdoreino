const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../apps/core/trilha_v4_assets/app.js'), 'utf8');
const bootstrap = {aluno:{nome:'Ana'},pessoa_id:'aluna-a',site_id:'mesh'};
function progress(){return {pessoa_id:'aluna-a',site_id:'mesh',atual_ordem:3,total_cents:0,meta_cents:null,meta_escolhida:false,
  etapas:Array.from({length:13},(_,i)=>({ordem:i+1,alcancada:i<3,conquista:'Registrada',meta_cents:null,alcancada_em:null}))};}
async function load(response, activityResponse){
  const nodes = new Map();
  const result = {};
  const context = vm.createContext({
    document:{querySelector(selector){
      if(!nodes.has(selector))nodes.set(selector,{textContent:selector==='#trilha-data'?JSON.stringify(bootstrap):'',removeAttribute(){},setAttribute(){},replaceChildren(){}});
      return nodes.get(selector);
    },addEventListener(){}},
    window:{location:{replace(url){result.redirect=url;}},addEventListener(){}},
    AbortController,setTimeout,clearTimeout,setInterval(){},
    fetch:async(url, options)=>{
      if(url==='/encomendas/minha-trilha/')return activityResponse||{ok:false,status:503};
      result.request={url,options};if(response instanceof Error)throw response;return response;
    },
  });
  vm.runInContext(source,context);
  context.renderJourney=payload=>{result.payload=JSON.parse(JSON.stringify(payload));};
  await new Promise(resolve=>setImmediate(resolve));
  result.nodes=nodes;result.context=context;
  return result;
}

test('carrega a jornada propria sem depender da ponte de rede do funil',async()=>{
  const data=progress();
  const r=await load({ok:true,status:200,json:async()=>data});
  assert.deepEqual(r.payload.progresso,{...data,etapas:data.etapas.map(step=>({...step,checklist:null}))});
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
  for(const mutate of [d=>d.pessoa_id='aluna-b',d=>d.site_id='outra-escola',d=>d.atual_ordem=13,d=>d.etapas.pop(),d=>d.meta_escolhida=true,d=>d.etapas[1].alcancada=false]){
    const data=progress();mutate(data);
    const r=await load({ok:true,status:200,json:async()=>data});
    assert.equal(r.payload,undefined);
    if(data.pessoa_id!==bootstrap.pessoa_id||data.site_id!==bootstrap.site_id){
      assert.equal(r.redirect,'/trilha/');assert.equal(r.nodes.get('main').hidden,true);
    }else assert.equal(r.nodes.get('.object-caption').textContent,'PROGRESSO INDISPONÍVEL');
  }
});

test('falhas da rede e do servidor nao viram progresso ficticio',async()=>{
  for(const response of [{ok:false,status:503},new Error('offline'),{ok:true,status:200,json:async()=>{throw new Error('invalid json');}}]){
    const r=await load(response);
    assert.equal(r.payload,undefined);
    assert.equal(r.nodes.get('.object-caption').textContent,'PROGRESSO INDISPONÍVEL');
  }
});

function withChecklist(){
  const data=progress();data.consultado_em='2026-10-10T19:00:00Z';
  data.etapas.forEach(step=>step.checklist={itens:[{id:`criterio-${step.ordem}`,titulo:step.conquista,estado:step.alcancada?'concluido':'pendente',detalhe:'Registro real',acao:null}],observacao:''});
  return data;
}
function ownActivities(items){return {pessoa_id:'aluna-a',site_id:'mesh',atividades:items};}
test('atividade real enriquece o proximo criterio sem promover a faixa',async()=>{
  const data=withChecklist();
  const activity={ordem:4,estado:'andamento',detalhe:'Trabalho aceito, produção iniciada.',acao:{rotulo:'Retomar trabalho',url:'/encomendas/fila/'}};
  const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>ownActivities([activity])});
  const checklist=r.context.journeyChecklist(r.payload.progresso,2,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['concluido','andamento']);
  assert.equal(checklist.itens[1].detalhe,activity.detalhe);
  assert.equal(r.payload.progresso.etapas[3].alcancada,false);
  assert.equal(r.payload.progresso.atual_ordem,3);
});
test('outra conta, falso concluido e acao externa nao entram no checklist',async()=>{
  for(const change of [d=>d.pessoa_id='outra',d=>d.site_id='outro',d=>d.atividades[0].estado='concluido',d=>d.atividades[0].acao.url='https://example.test',d=>d.atividades[0].acao.url='/admin/trilha/']){
    const data=withChecklist();
    const activity=ownActivities([{ordem:4,estado:'andamento',detalhe:'NÃO MOSTRAR',acao:{rotulo:'Retomar',url:'/encomendas/fila/'}}]);change(activity);
    const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>activity});
    const checklist=r.context.journeyChecklist(r.payload.progresso,2,r.payload.atividades);
    assert.equal(checklist.itens[1].estado,'pendente');
    assert.doesNotMatch(JSON.stringify(checklist),/NÃO MOSTRAR/);
    assert.match(checklist.observacao,/Não foi possível consultar/);
  }
});
test('trabalho cancelado retorna pendente e uma conquista registrada permanece concluida',async()=>{
  const data=withChecklist();
  const activities=ownActivities([{ordem:3,estado:'andamento',detalhe:'Outro trabalho iniciado',acao:null},{ordem:4,estado:'pendente',detalhe:'Trabalho cancelado.',acao:null}]);
  const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>activities});
  const checklist=r.context.journeyChecklist(r.payload.progresso,2,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['concluido','pendente']);
  assert.equal(checklist.itens[1].detalhe,'Trabalho cancelado.');
  assert.equal(checklist.itens[0].detalhe,'Registro real');
});
test('consulta de faixa passada mostra apenas seus criterios e nao a meta da atual',async()=>{
  const data=withChecklist();
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,1,r.payload.atividades);
  assert.equal(checklist.itens.length,1);
  assert.equal(checklist.itens[0].id,'criterio-2');
});

test('branca mostra quatro requisitos com os tres destinos e envio separado, inclusive depois da conquista',async()=>{
  for(const current of [1,3]){
    const data=withChecklist();data.atual_ordem=current;
    data.etapas.forEach(step=>step.alcancada=step.ordem<=current);
    const urls=['/conquistas/inicio/motivo/','/conquistas/inicio/objetivo/','/conquistas/inicio/item/','/conquistas/inicio/item/#inicio-form-item'];
    data.etapas[1].checklist.itens=['motivo-2','plano-2','item-2','envio-2'].map((id,i)=>({id,titulo:['Meu motivo','Meu objetivo e compromisso','Meu primeiro item 3D','Enviar meu 3D'][i],estado:i===0?'concluido':'pendente',detalhe:'Registro privado',acao:{rotulo:'Abrir',url:urls[i]}}));
    const r=await load({ok:true,status:200,json:async()=>data});
    const checklist=r.context.journeyChecklist(r.payload.progresso,0,r.payload.atividades);
    assert.deepEqual(Array.from(checklist.itens,item=>item.id),['motivo-2','plano-2','item-2','envio-2']);
    assert.deepEqual(Array.from(checklist.itens,item=>item.acao.url),urls);
    // Executa o gerador dos botões com nós mínimos, sem substituir sua lógica.
    r.context.document.createElement=tag=>({tag,children:[],dataset:{},setAttribute(){},append(...children){this.children.push(...children);}});
    const block=r.context.whiteBeltActions(r.payload.progresso);
    const list=block.children.find(node=>node.tag==='ol');
    assert.equal(list.children.length,4);
    assert.deepEqual(list.children.map(row=>row.children[0].href),urls);
    assert.equal(list.children[0].children[0].dataset.estado,'concluido');
    assert.match(block.children.find(node=>node.className==='white-belt-count').textContent,/1 de 4/);
  }
});
test('checklist ausente durante atualizacao nao vira etapas inventadas',async()=>{
  const r=await load({ok:true,status:200,json:async()=>progress()});
  const checklist=r.context.journeyChecklist(r.payload.progresso,2,r.payload.atividades);
  assert.equal(checklist.disponivel,false);assert.equal(checklist.itens.length,0);
});

test('aluno amarelo com quatro requisitos concluidos continua vendo a pratica seguinte',async()=>{
  const data=withChecklist();data.atual_ordem=2;
  data.etapas.forEach(step=>step.alcancada=step.ordem<=2);
  data.etapas[1].checklist.itens=['motivo-2','plano-2','item-2','envio-2'].map(id=>({id,titulo:id,estado:'concluido',detalhe:'Requisito concluído',acao:{rotulo:'Abrir',url:'/conquistas/inicio/motivo/'}}));
  data.etapas[2].checklist.itens[0].estado='pendente';
  data.etapas[2].checklist.itens[0].acao={rotulo:'Abrir Sandbox',url:'/encomendas/sandbox/'};
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,1,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.id),['item-2','criterio-3']);
  assert.equal(checklist.itens.find(item=>item.estado==='pendente').acao.url,'/encomendas/sandbox/');
  assert.equal(r.context.journeyChecklist(r.payload.progresso,0,r.payload.atividades).itens.length,4);
});
test('estados ou acoes invalidas no checklist nao sao desenhados',async()=>{
  for(const change of [d=>d.etapas[0].checklist.itens[0].estado='suposto',d=>d.etapas[0].checklist.itens[0].acao={rotulo:'Falso',url:'javascript:alert(1)'},d=>d.etapas[0].checklist.itens.push(d.etapas[0].checklist.itens[0])]){
    const data=withChecklist();change(data);
    const r=await load({ok:true,status:200,json:async()=>data});
    assert.equal(r.payload,undefined);
  }
});


test('meta pessoal compartilhada entre graus conta uma vez no checklist',async()=>{
  const data=withChecklist();data.atual_ordem=6;data.meta_escolhida=true;data.meta_cents=10000;data.total_cents=150;
  data.etapas.forEach((step,i)=>{step.alcancada=i<6;step.meta_cents=i>=5?125*(i-4):null;step.checklist.itens[0].estado=step.alcancada?'concluido':'andamento';});
  for(const step of data.etapas.slice(5))step.checklist.itens.unshift({id:`meta-${step.ordem}`,titulo:'Escolher minha meta pessoal',estado:'concluido',detalhe:'Meta pessoal escolhida.',acao:null});
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,5,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.id),['meta-6','criterio-6','criterio-7']);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['concluido','concluido','andamento']);
});
