const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const root=require('node:path').resolve(__dirname, '../../..') + '/';
const sw=fs.readFileSync(root+'services/funil/static/funil/sw.js','utf8');
function worker(){
  const listeners={},shown=[],opened=[];
  const context=vm.createContext({URL,self:{location:{href:'https://meshcraft.top/sw.js',origin:'https://meshcraft.top'},
    clients:{matchAll:async()=>[],openWindow:async(path)=>opened.push(path)},
    AVISOS_DO_SITE:{textos:{'gamificacao.conquista-concedida':{titulo:'Medalha',corpo:'Medalha recebida'}},
      links:{'gamificacao.conquista-concedida':'/trilha/'},caminho:'/notificacoes',generico:{titulo:'Aviso',corpo:'Novo'},
      faixas:{vermelha:'Vermelha',preta_grau_2:'Preta · 2º grau'},faixa_titulo:'Você mudou de faixa!',grau_titulo:'Novo grau!',faixa_corpo:'Você chegou à faixa'},
    addEventListener:(name,fn)=>listeners[name]=fn,
    registration:{showNotification:async(title,options)=>shown.push({title,...options})}}});
  vm.runInContext(sw,context);
  return {shown,opened,
    click:async(caminho)=>{let pending;listeners.notificationclick({notification:{data:{caminho},close(){}},waitUntil:p=>pending=p});await pending;},
    push:async(carta)=>{let pending;listeners.push({data:{json:()=>carta},waitUntil:p=>pending=p});await pending;}};
}
test('toque em aviso antigo ja exibido abre a Trilha e preserva outros destinos',async()=>{
  const r=worker();
  for (const caminho of ['/conquistas/','/conquistas/trilha/medalhas/','https://meshcraft.top/conquistas/']) {
    await r.click(caminho);assert.equal(r.opened.at(-1),'/trilha/');
  }
  await r.click('/forms/sugestoes/sugestoes/12');
  assert.equal(r.opened.at(-1),'/forms/sugestoes/sugestoes/12');
});
test('celular mostra faixa e grau reais com destino Trilha',async()=>{
  const r=worker();
  await r.push({assunto:'gamificacao.conquista-concedida',parametros:{conquista_slug:'trilha-faixa-vermelha'}});
  assert.equal(r.shown[0].title,'Você mudou de faixa!');assert.match(r.shown[0].body,/Vermelha/);assert.equal(r.shown[0].data.caminho,'/trilha/');
  await r.push({assunto:'gamificacao.conquista-concedida',parametros:{conquista_slug:'trilha-faixa-preta-grau-2'}});
  assert.equal(r.shown[1].title,'Novo grau!');assert.match(r.shown[1].body,/2º grau/);
});
test('celular preserva medalha e nao reapresenta nivel antigo',async()=>{
  const r=worker();
  await r.push({assunto:'gamificacao.nivel-alcancado',parametros:{nivel:9}});assert.equal(r.shown.length,0);
  await r.push({assunto:'gamificacao.conquista-concedida',parametros:{conquista_slug:'mao-amiga'}});assert.equal(r.shown[0].title,'Medalha');
});
test('celebracao so e confirmada por gesto e manda a propria identidade',async()=>{
  const source=fs.readFileSync(root+'services/funil/apps/core/trilha_v4_assets/app.js','utf8');
  const ceremony=fs.readFileSync(root+'services/gamificacao/static/faixa_cerimonia.js','utf8');
  class Element {
    constructor(tag){this.tag=tag;this.dataset={};this.children=[];this.events={};this.style={setProperty(){}};this.classList={add(){},remove(){}};this.isConnected=true;this._text='';}
    set textContent(v){this._text=v;} get textContent(){return this._text+this.children.map(n=>n.textContent).join(' ');}
    get childNodes(){return this.children;}
    append(...n){this.children.push(...n);} replaceChildren(...n){this.children=n;}
    setAttribute(){} addEventListener(k,fn){this.events[k]=fn;} focus(){} showModal(){this.open=true;}
    close(){this.open=false;} remove(){this.isConnected=false;}
  }
  const body=new Element('body'),timers=[];let call;
  const context=vm.createContext({URL,FormData,Event,
    window:{addEventListener(){},dispatchEvent(){},matchMedia:()=>({matches:true})},
    refreshJourney(){},setTimeout:fn=>(timers.push(fn),timers.length),clearTimeout(){},
    document:{body,documentElement:new Element('html'),activeElement:new Element('a'),
      currentScript:{src:'https://meshcraft.top/trilha/faixas-static/faixa_cerimonia.js'},querySelector:()=>null,createElement:t=>new Element(t)},
    fetch:async(url,options)=>{call={url,options};return {ok:true};}});
  vm.runInContext(ceremony,context);
  vm.runInContext(source.slice(source.indexOf('\nfunction celebrateJourney')),context);
  const progress={pessoa_id:'aluna',site_id:'mesh',atual_ordem:4,celebracao:{ordem:4,tipo:'cor',bonus_xp:5000},csrf:'csrf-teste',etapas:[{ordem:4,nome:'Vermelha',alcancada:true}]};
  context.celebrateJourney(progress,{pessoa_id:'aluna',site_id:'mesh'});
  const all=(n=body)=>[n,...n.children.flatMap(c=>all(c))];
  const click=async text=>{const button=all().find(n=>n.tag==='button'&&n.textContent.includes(text));assert.ok(button);await button.events.click({target:button});};
  assert.equal(call,undefined);
  await click('VER MINHA CONQUISTA');timers.at(-1)();assert.match(body.textContent,/VERMELHA/);
  assert.equal(call,undefined);
  await click('CONTINUAR MINHA JORNADA');
  assert.equal(call.url,'/trilha/inventario/api/');assert.equal(call.options.body.get('contexto_pessoa'),'aluna');
  assert.equal(call.options.body.get('ordem'),'4');assert.equal(call.options.headers['X-CSRFToken'],'csrf-teste');
});
