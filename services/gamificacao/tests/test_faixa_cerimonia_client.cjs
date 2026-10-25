const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../static/faixa_cerimonia.js'),'utf8');
class Element {
  constructor(tag){this.tag=tag;this.childNodes=[];this.events={};this.attrs={};this.style={setProperty(){}};this.classList={add(){},remove(){}};this._text='';this.isConnected=true;}
  set textContent(v){this._text=v;}
  get textContent(){return this._text+this.childNodes.map(n=>n.textContent).join(' ');}
  append(...nodes){this.childNodes.push(...nodes);}
  replaceChildren(...nodes){this.childNodes=nodes;}
  setAttribute(k,v){this.attrs[k]=v;}
  addEventListener(k,fn){this.events[k]=fn;}
  focus(){}
  showModal(){this.open=true;}
  close(){this.open=false;}
  remove(){this.isConnected=false;}
  get dataset(){return this._dataset ||= {};}
}
function setup({failed=false,reduced=false}={}){
  const body=new Element('body'),calls=[],timers=[],events=[];
  const document={body,documentElement:new Element('html'),activeElement:new Element('a'),currentScript:{src:'https://meshcraft.top/trilha/faixas-static/faixa_cerimonia.js'},
    hidden:false,createElement:t=>new Element(t),querySelector:()=>null,addEventListener(){}};
  const window={matchMedia:()=>({matches:reduced}),dispatchEvent:e=>events.push(e.type),addEventListener(){}};
  const sandbox={document,window,URL,FormData,Event,setTimeout:fn=>(timers.push(fn),timers.length),clearTimeout(){},setInterval(){},
    fetch:async(url,options)=>{calls.push({url,options});return {ok:!failed};}};
  vm.runInNewContext(source,sandbox);
  const all=(n=body)=>[n,...n.childNodes.flatMap(c=>all(c))];
  const click=async text=>{const b=all().find(n=>n.tag==='button'&&n.textContent.includes(text));assert.ok(b,'Botão '+text);await b.events.click({target:b});return b;};
  return {api:window.MeshcraftFaixas,body,calls,timers,events,all,click,text:()=>body.textContent};
}
const names=['Branca','Amarela','Azul','Vermelha','Verde','Marrom','Preta','Preta · Grau II','Preta · Grau III','Preta · Grau IV','Preta · Grau V','Preta · Grau VI','Preta · Grau VII'];
function progress(order){
  return {pessoa_id:'a',site_id:'mesh',csrf:'csrf-de-teste',atual_ordem:order,
    etapas:names.map((nome,i)=>({ordem:i+1,nome,alcancada:i<order,conquista:'Realização avaliada'})),
    celebracao:{ordem:order,tipo:order>7?'grau':'cor',bonus_xp:order*5000}};
}
test('todas as cores e graus passam por tarefa, revelação e conquista com XP separado',async()=>{
  for(let order=2;order<=13;order++){
    const ui=setup(),data=progress(order);
    assert.equal(ui.api.celebrar(data,data,{tarefa:{titulo:'Tarefa concluída',xp:100}}),true);
    assert.match(ui.text(),/100 XP/);assert.doesNotMatch(ui.text(),/BÔNUS DA FAIXA/);
    await ui.click('VER MINHA CONQUISTA');assert.match(ui.text(),/ESSE MOMENTO É SEU/);
    assert.doesNotMatch(ui.text(),/100 XP|BÔNUS DA FAIXA/);
    ui.timers.at(-1)();
    assert.match(ui.text(),new RegExp('FAIXA '+names[order-1].toUpperCase().replace(' · ',' · ')));
    assert.match(ui.text(),/BÔNUS DA FAIXA/);assert.doesNotMatch(ui.text(),/XP DA TAREFA/);
    if(order>=7)assert.ok(ui.all().some(n=>n.className==='mc-degree'));
    await ui.click('CONTINUAR MINHA JORNADA');
    assert.equal(ui.calls.length,1);assert.equal(ui.calls[0].options.body.get('acao'),'celebracao-vista');
    assert.equal(ui.calls[0].options.body.get('ordem'),String(order));
    assert.equal(ui.api.ativo(),false);
  }
});
test('nenhuma tela celebra etapa pendente, outra conta ou XP inventado',()=>{
  for(const mutate of [d=>d.etapas[1].alcancada=false,d=>d.celebracao.bonus_xp=-1,d=>d.celebracao.bonus_xp='5000',d=>d.atual_ordem=1]){
    const ui=setup(),d=progress(2);mutate(d);assert.equal(ui.api.celebrar(d,d),false);assert.equal(ui.calls.length,0);
  }
  const ui=setup(),d=progress(2);assert.equal(ui.api.celebrar(d,{...d,pessoa_id:'outra'}),false);
});
test('a fila mostra cada faixa em ordem sem abrir sobre outra celebração',async()=>{
  const ui=setup(),d=progress(3);
  d.celebracao={ordem:2,fila:[{ordem:2,bonus_xp:5000},{ordem:3,bonus_xp:10000}]};
  ui.api.celebrar(d,d);assert.equal(ui.api.celebrar(d,d),false);
  await ui.click('VER MINHA CONQUISTA');ui.timers.at(-1)();assert.match(ui.text(),/FAIXA AMARELA/);
  await ui.click('VER A PRÓXIMA CONQUISTA');assert.match(ui.text(),/Sua conquista 2 de 2/);
  await ui.click('VER MINHA CONQUISTA');ui.timers.at(-1)();assert.match(ui.text(),/FAIXA AZUL/);
  await ui.click('CONTINUAR MINHA JORNADA');
  assert.deepEqual(ui.calls.map(c=>c.options.body.get('ordem')),['2','3']);
});
test('falha ao confirmar permite tentar novamente; fechar preserva a pendência',async()=>{
  const ui=setup({failed:true}),d=progress(2);
  ui.api.celebrar(d,d,{revelar:true});ui.timers.at(-1)();
  const button=await ui.click('CONTINUAR MINHA JORNADA');
  assert.equal(button.disabled,false);assert.match(ui.text(),/Sua conquista está salva/);assert.equal(ui.api.ativo(),true);
  await ui.click('×');assert.equal(ui.api.ativo(),false);assert.equal(d.celebracao.ordem,2);
  assert.equal(ui.api.celebrar(d,d),false);
});
test('demonstração e movimento reduzido não escrevem registros',async()=>{
  const ui=setup({reduced:true}),d=progress(7);
  ui.api.celebrar(d,d,{demonstracao:true,revelar:true});ui.timers.at(-1)();
  assert.match(ui.text(),/DEMONSTRAÇÃO VISUAL/);await ui.click('CONTINUAR MINHA JORNADA');assert.equal(ui.calls.length,0);
});

