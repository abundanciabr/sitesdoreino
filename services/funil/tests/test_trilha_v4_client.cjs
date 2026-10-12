const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../apps/core/trilha_v4_assets/app.js'), 'utf8');
const bootstrap = {aluno:{nome:'Ana'},pessoa_id:'aluna-a',site_id:'mesh'};
function progress(current=3,caminho='freelancer'){
  const names=['Branca','Amarela','Azul','Vermelha','Verde','Marrom','Preta'];
  const total=caminho==='freelancer'?13:7;
  return {pessoa_id:'aluna-a',site_id:'mesh',caminho,graus_historicos:[],atual_ordem:current,
    total_cents:0,meta_cents:null,meta_escolhida:false,
    etapas:Array.from({length:total},(_,i)=>({ordem:i+1,nome:names[i]||`Preta ${i-5} Grau`,
      alcancada:i<current,conquista:'Realização avaliada',meta_cents:null,alcancada_em:null}))};
}
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
  assert.equal(r.request.url,'/trilha/minha-trilha/');
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

function withChecklist(current=3,caminho='freelancer'){
  const data=progress(current,caminho);data.consultado_em='2026-10-10T19:00:00Z';
  const item=(id,titulo,estado,acao=null,bloqueado=false)=>({id,titulo,estado,detalhe:'Registro real',acao,bloqueado});
  data.etapas.forEach(step=>{
    const estado=step.alcancada?'concluido':'pendente';
    const ordem=step.ordem;
    const itens=ordem===1?[item('criterio-1','Começar minha jornada','concluido')]
      :ordem===2?[item('motivo-2','Meu motivo',estado,{rotulo:'Escolher meu caminho',url:'/trilha/inicio/motivo/'}),
                   item('plano-2','Meu compromisso',estado,{rotulo:'Assumir meu compromisso',url:'/trilha/inicio/objetivo/'})]
      :ordem===3?[item('item-3','Relatar meu primeiro item 3D',estado,{rotulo:'Descrever meu item',url:'/trilha/inicio/item/'})]
      :ordem===4?[item('envio-4','Apresentar meu item para análise',estado,{rotulo:'Apresentar meu item',url:'/trilha/inicio/envio/'})]
      :[item(`criterio-${ordem}`,ordem===5&&caminho==='freelancer'?'Concluir prática no Sandbox':ordem===6&&caminho==='freelancer'?'Entregar trabalho da Fila':step.conquista,estado,
        {rotulo:'Abrir atividade',url:caminho==='freelancer'&&ordem===5?'/trilha/sandbox/':caminho==='freelancer'&&ordem===6?'/trilha/fila/':'/trilha/ciclo/'})];
    step.checklist={itens,observacao:''};
  });
  return data;
}
function ownActivities(items){return {pessoa_id:'aluna-a',site_id:'mesh',atividades:items};}
test('atividade real enriquece o proximo criterio sem promover a faixa',async()=>{
  const data=withChecklist(5);
  const activity={ordem:6,estado:'andamento',detalhe:'Trabalho aceito, produção iniciada.',acao:{rotulo:'Retomar trabalho',url:'/encomendas/fila/'}};
  const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>ownActivities([activity])});
  const checklist=r.context.journeyChecklist(r.payload.progresso,4,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['andamento']);
  assert.equal(checklist.itens[0].detalhe,activity.detalhe);
  assert.equal(r.payload.progresso.etapas[5].alcancada,false);
  assert.equal(r.payload.progresso.atual_ordem,5);
});
test('outra conta, falso concluido e acao externa nao entram no checklist',async()=>{
  for(const change of [d=>d.pessoa_id='outra',d=>d.site_id='outro',d=>d.atividades[0].estado='concluido',d=>d.atividades[0].acao.url='https://example.test',d=>d.atividades[0].acao.url='/admin/trilha/',d=>d.atividades[0].acao.url='/conquistas/']){
    const data=withChecklist(5);
    const activity=ownActivities([{ordem:6,estado:'andamento',detalhe:'NÃO MOSTRAR',acao:{rotulo:'Retomar',url:'/encomendas/fila/'}}]);change(activity);
    const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>activity});
    const checklist=r.context.journeyChecklist(r.payload.progresso,4,r.payload.atividades);
    assert.equal(checklist.itens[0].estado,'pendente');
    assert.doesNotMatch(JSON.stringify(checklist),/NÃO MOSTRAR/);
    assert.match(checklist.observacao,/Não foi possível consultar/);
  }
});
test('trabalho cancelado retorna pendente e uma conquista registrada permanece concluida',async()=>{
  const data=withChecklist(5);
  const activities=ownActivities([{ordem:5,estado:'andamento',detalhe:'Outro trabalho iniciado',acao:null},{ordem:6,estado:'pendente',detalhe:'Trabalho cancelado.',acao:null}]);
  const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>activities});
  const checklist=r.context.journeyChecklist(r.payload.progresso,4,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['pendente']);
  assert.equal(checklist.itens[0].detalhe,'Trabalho cancelado.');
  const anterior=r.context.journeyChecklist(r.payload.progresso,3,r.payload.atividades);
  assert.equal(anterior.itens[0].estado,'concluido');
  assert.equal(anterior.itens[0].detalhe,'Registro real');
});
test('consulta de faixa passada mostra apenas seus criterios e nao a meta da atual',async()=>{
  const data=withChecklist();
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,1,r.payload.atividades);
  assert.equal(checklist.itens.length,1);
  assert.deepEqual(Array.from(checklist.itens,item=>item.id),['item-3']);
});

function mountPanel(context){
  context.document.createElement=tag=>({tag,children:[],dataset:{},style:{},attributes:{},
    addEventListener(){},
    setAttribute(key,value){this.attributes[key]=value;},
    insertAdjacentHTML(position,value){this.innerHTML=(this.innerHTML||'')+value;},
    append(...children){this.children.push(...children);}});
}
function descendants(node){return [node,...(node.children||[]).flatMap(descendants)];}

test('branca libera somente motivo e compromisso em sequencia',async()=>{
  for(let done=0;done<=2;done++){
    const data=withChecklist();data.atual_ordem=done===2?2:1;
    data.etapas.forEach(step=>step.alcancada=step.ordem<=data.atual_ordem);
    const urls=['/trilha/inicio/motivo/','/trilha/inicio/objetivo/'];
    data.etapas[1].checklist.itens=['motivo-2','plano-2'].map((id,i)=>({id,titulo:['Meu motivo','Meu compromisso'][i],estado:i<done?'concluido':i===done?'andamento':'pendente',bloqueado:i>done,detalhe:'Registro privado',acao:{rotulo:'Abrir',url:urls[i]}}));
    const r=await load({ok:true,status:200,json:async()=>data});
    const checklist=r.context.journeyChecklist(r.payload.progresso,0,r.payload.atividades);
    assert.deepEqual(Array.from(checklist.itens,item=>item.id),['motivo-2','plano-2']);
    assert.deepEqual(Array.from(checklist.itens,item=>item.acao.url),urls);
    // Executa o gerador dos botões com nós mínimos, sem substituir sua lógica.
    mountPanel(r.context);
    const block=r.context.whiteBeltActions(r.payload.progresso);
    const list=block.children.find(node=>node.tag==='ol');
    assert.equal(list.children.length,2);
    assert.deepEqual(descendants(list).filter(node=>node.tag==='a').map(node=>node.href),urls.slice(0,Math.min(done+1,2)));
    assert.equal(descendants(list).filter(node=>node.className==='primary checklist-action').length,done===2?0:1);
    list.children.forEach((row,i)=>{
      if(i>done){assert.equal(row.attributes['aria-disabled'],'true');assert.equal(descendants(row).filter(node=>node.href).length,0);assert.match(row.children[2].innerHTML,/#lock/);assert.equal(row.children[2].textContent,'Pendente');}
    });
    assert.equal(descendants(block).find(node=>node.className==='checklist-percent').textContent,`${done*50}%`);
    assert.equal(descendants(block).find(node=>node.attributes?.role==='progressbar').attributes['aria-valuenow'],String(done*50));
    assert.ok(block.children.indexOf(block.children.find(node=>node.className==='checklist-completion'))<block.children.indexOf(list));
  }
});

test('registros antigos nao liberam tarefas posteriores quando falta um passo anterior',async()=>{
  const data=withChecklist();
  data.etapas[1].checklist.itens=['motivo-2','plano-2'].map((id,i)=>({id,titulo:`Passo ${i+1}`,estado:i===0?'pendente':'concluido',detalhe:'Legado',acao:{rotulo:'Abrir',url:'/trilha/inicio/objetivo/'}}));
  const r=await load({ok:true,status:200,json:async()=>data});
  const details=r.context.journeyChecklist(r.payload.progresso,0);
  assert.deepEqual(Array.from(details.itens,item=>item.bloqueado),[false,true]);
  assert.deepEqual(Array.from(details.itens,item=>item.estado),['pendente','pendente']);
});

test('o mesmo painel atende todas as faixas com numeros reais e sem criar tarefas',async()=>{
  const r=await load({ok:true,status:200,json:async()=>withChecklist()});mountPanel(r.context);
  for(let i=1;i<=13;i++){
    const details={disponivel:true,itens:[{titulo:'Prática registrada',estado:'concluido',detalhe:'Registro real'},{titulo:'Prática em curso',estado:'andamento',detalhe:'Trabalho salvo',acao:{rotulo:'Continuar',url:'/encomendas/sandbox/'}}],observacao:''};
    const block=r.context.createProgressPanel(details,{name:String(i),number:String(i).padStart(2,'0'),modal:true});
    assert.equal(block.children.find(node=>node.tag==='ol').children.length,2);
    assert.equal(descendants(block).find(node=>node.className==='checklist-percent').textContent,'50%');
    assert.equal(descendants(block).find(node=>node.id==='dialog-title').textContent,'Um passo de cada vez.');
  }
});
test('checklist ausente durante atualizacao nao vira etapas inventadas',async()=>{
  const r=await load({ok:true,status:200,json:async()=>progress()});
  const checklist=r.context.journeyChecklist(r.payload.progresso,2,r.payload.atividades);
  assert.equal(checklist.disponivel,false);assert.equal(checklist.itens.length,0);
});

test('amarela mostra o primeiro item sem repetir motivo ou compromisso da branca',async()=>{
  const data=withChecklist(2);
  data.etapas.forEach(step=>step.alcancada=step.ordem<=2);
  data.etapas[1].checklist.itens=['motivo-2','plano-2'].map((id,i)=>({id,titulo:id,estado:'concluido',detalhe:'Requisito concluído',acao:{rotulo:'Abrir',url:i===0?'/trilha/inicio/motivo/':'/trilha/inicio/objetivo/'}}));
  data.etapas[2].checklist.itens[0].estado='pendente';
  data.etapas[2].checklist.itens[0].acao={rotulo:'Descrever meu item',url:'/trilha/inicio/item/'};
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,1,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.id),['item-3']);
  assert.equal(checklist.itens.find(item=>item.estado==='pendente').acao.url,'/trilha/inicio/item/');
  assert.equal(r.context.journeyChecklist(r.payload.progresso,0,r.payload.atividades).itens.length,2);
});
test('avaliacao do Sandbox preserva a explicacao e mostra resultado legivel',async()=>{
  const data=withChecklist();data.atual_ordem=2;
  data.etapas.forEach(step=>step.alcancada=step.ordem<=2);
  data.avaliacoes_sandbox=[{trabalho_id:'trabalho-1',entrega_id:'entrega-2',analise_id:'analise-2',
    versao:2,atual:true,historico:false,estado:'concluida',resultado:'atende',
    explicacao:'<script>texto da análise</script>',justificativa:'Peça examinada.',
    proxima_acao:'Aguarde o registro da conquista.',url:'/encomendas/sandbox/trabalhos/trabalho-1/',
    reconhecimento:{estado:'aguardando_sequencia',texto:'A sequência da jornada ainda está pendente.'}}];
  const r=await load({ok:true,status:200,json:async()=>data});mountPanel(r.context);
  const card=r.context.sandboxEvaluationPanel(r.payload.progresso.avaliacoes_sandbox);
  const all=descendants(card);
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-explanation').textContent,'<script>texto da análise</script>');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-result').textContent,'Atende ao pedido');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-version').textContent,'Versão 2 · Atual neste trabalho');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-next').textContent,'Aguarde o registro da conquista.');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-recognition').textContent,'A sequência da jornada ainda está pendente.');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-link').href,'/encomendas/sandbox/trabalhos/trabalho-1/');
  assert.equal(all.find(n=>n.className==='sandbox-evaluation-explanation').innerHTML,undefined);
});
test('avaliacao ausente ou link inseguro nao inventa conquista nem cria link',async()=>{
  const r=await load({ok:true,status:200,json:async()=>withChecklist()});mountPanel(r.context);
  const missing=r.context.sandboxEvaluationPanel(undefined);
  assert.match(descendants(missing).find(n=>n.className==='sandbox-evaluations-empty').textContent,/Não foi possível consultar/);
  const item={versao:1,atual:false,historico:true,estado:'pendente',resultado:'',explicacao:'Entrega recebida.',justificativa:'',proxima_acao:'',url:'https://example.test/',reconhecimento:{estado:'aguardando_analise',texto:'A análise não terminou.'}};
  const card=r.context.sandboxEvaluationPanel([item]);
  assert.equal(descendants(card).filter(n=>n.tag==='a').length,0);
  assert.equal(descendants(card).find(n=>n.className==='sandbox-evaluation-recognition').textContent,'A análise não terminou.');
});
test('estados ou acoes invalidas no checklist nao sao desenhados',async()=>{
  for(const change of [d=>d.etapas[0].checklist.itens[0].estado='suposto',d=>d.etapas[0].checklist.itens[0].acao={rotulo:'Falso',url:'javascript:alert(1)'},d=>d.etapas[0].checklist.itens[0].acao={rotulo:'Falso',url:'/conquistas/'},d=>d.etapas[0].checklist.itens.push(d.etapas[0].checklist.itens[0])]){
    const data=withChecklist();change(data);
    const r=await load({ok:true,status:200,json:async()=>data});
    assert.equal(r.payload,undefined);
  }
});


test('meta pessoal compartilhada entre graus conta uma vez no checklist',async()=>{
  const data=withChecklist(8);data.meta_escolhida=true;data.meta_cents=10000;data.total_cents=150;
  data.etapas.forEach((step,i)=>{step.meta_cents=i>=7?125*(i-6):null;step.checklist.itens[0].estado=step.alcancada?'concluido':'andamento';});
  for(const step of data.etapas.slice(7))step.checklist.itens.unshift({id:`meta-${step.ordem}`,titulo:'Escolher minha meta pessoal',estado:'concluido',detalhe:'Meta pessoal escolhida.',acao:null});
  const r=await load({ok:true,status:200,json:async()=>data});
  const checklist=r.context.journeyChecklist(r.payload.progresso,7,r.payload.atividades);
  assert.deepEqual(Array.from(checklist.itens,item=>item.id),['meta-9','criterio-9']);
  assert.deepEqual(Array.from(checklist.itens,item=>item.estado),['concluido','andamento']);
});

test('caminhos curtos usam sete faixas e não herdam Sandbox ou Fila do freelancer',async()=>{
  for(const caminho of ['ugc','jogo','aprender']){
    const data=withChecklist(5,caminho);
    const externa=ownActivities([{ordem:6,estado:'andamento',detalhe:'NÃO MOSTRAR',acao:{rotulo:'Fila',url:'/encomendas/fila/'}}]);
    const r=await load({ok:true,status:200,json:async()=>data},{ok:true,status:200,json:async()=>externa});
    assert.equal(r.payload.progresso.etapas.length,7);
    const checklist=r.context.journeyChecklist(r.payload.progresso,4,r.payload.atividades);
    assert.deepEqual(Array.from(checklist.itens,item=>item.id),['criterio-6']);
    assert.equal(checklist.itens[0].acao.url,'/trilha/ciclo/');
    assert.doesNotMatch(JSON.stringify(checklist),/NÃO MOSTRAR/);
  }
});

test('tarefas pertencem a um unico painel nos quatro caminhos, atuais e historicos',async()=>{
  for(const caminho of ['freelancer','ugc','jogo','aprender']){
    const total=caminho==='freelancer'?13:7;
    for(const current of [1,2,4,total]){
      const data=withChecklist(current,caminho);
      const r=await load({ok:true,status:200,json:async()=>data});
      const before=JSON.stringify(r.payload.progresso);
      const shown=new Set();
      for(let index=0;index<current;index++){
        const details=r.context.journeyChecklist(r.payload.progresso,index,r.payload.atividades);
        if(index===total-1){assert.equal(details.concluido,true);assert.equal(details.itens.length,0);continue;}
        assert.deepEqual(Array.from(details.itens,item=>item.id),data.etapas[index+1].checklist.itens.map(item=>item.id));
        for(const item of details.itens){assert.equal(shown.has(item.id),false);shown.add(item.id);}
      }
      assert.equal(JSON.stringify(r.payload.progresso),before);
    }
  }
});

test('ultimo marco concluido mostra a conclusao sem repetir tarefas ou progresso zero',async()=>{
  const data=withChecklist(7,'jogo');
  const r=await load({ok:true,status:200,json:async()=>data});mountPanel(r.context);
  const details=r.context.journeyChecklist(r.payload.progresso,6,r.payload.atividades);
  const panel=r.context.createProgressPanel(details,{name:'Preta',number:'07',summary:'Percurso concluído'});
  assert.match(descendants(panel).find(node=>node.className==='progress-note').textContent,/concluiu todas as etapas/);
  assert.equal(descendants(panel).filter(node=>node.tag==='ol'||node.attributes?.role==='progressbar').length,0);
  const incompleto=await load({ok:true,status:200,json:async()=>withChecklist(4,'jogo')});
  assert.equal(incompleto.context.journeyChecklist(incompleto.payload.progresso,6,incompleto.payload.atividades).concluido,false);
});
