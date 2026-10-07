import {criar} from './editor.js?v=2';
const config=JSON.parse(document.getElementById('dia1-config').textContent),root=document.getElementById('dia1');
const $=id=>root.querySelector('#d1-'+id),state=config.estado,csrf=root.querySelector('[name=csrfmiddlewaretoken]').value;
const resumeVideo=state.video;
let revision=state.revisao,engine=null,tool='girar',referenceMode=false,timer=null,saving=null,dirty=false,conflict=false,finished=config.legado,translating=false,sending=false,videoCheckpoint=state.video;
const steps=[
 ['Boas-vindas e trato da semana','Hoje você começa um pedido. Veja como a semana funciona e continue quando estiver pronto.','welcome','Dia 1 de 7. Eu sou a Lívia, e essa semana eu não vou te dar aula. Eu vou te dar um cliente.'],
 ['O pedido chega','Alex mandou uma mensagem em inglês. Traduza o pedido para entender o que ele precisa.','conversation','Relaxa: eu também não sabia quando comecei.'],
 ['Responda ao Alex','Escreva em português, traduza e confira o inglês antes de enviar na conversa simulada.','conversation','Leu? Ele tem uma loja e quer um fone colorido com orelhas de gato. Agora a gente responde.'],
 ['Pedido fechado','Veja sua resposta na conversa e a confirmação do Alex. O pedido é simulado. Agora vamos atender.','conversation','Fechado. Você acabou de fechar um pedido com um cliente de outro país sem falar uma palavra de inglês. Copiar e colar. É isso.'],
 ['Girar · conheça o seu cubo','Arraste em volta do cubo para girar a vista, com o mouse ou com o dedo.','model','Esse cubo é o seu material de trabalho. Quase tudo que eu faço começa com um cubo.'],
 ['Esticar · a primeira forma','Escolha Esticar e arraste o cubo para cima até ele ficar mais alto do que largo.','model','Não tem medida certa, é no olho.'],
 ['Afinar · o pulo do gato','Escolha Afinar e arraste a ponta de cima para dentro. Veja o cubo virar orelha.','model','Agora o pulo do gato, literalmente. Olha o cubo virando orelha.'],
 ['Mover · a orelha à esquerda','Volte à vista de frente. Escolha Mover e arraste a orelha para o lado esquerdo do arco do fone.','model','Ficou torta? Tem o Desfazer ali. Você não estraga nada aqui.'],
 ['Olhar · confira todos os lados','Escolha Girar novamente. Observe sua orelha por outros ângulos.','model','Isso que tá na sua tela é um objeto 3D feito por você. Agora há pouco você nunca tinha feito um.'],
 ['No Blender de verdade','Acompanhe a sequência indicada na prévia. Sua orelha continua guardada aqui.','blender','Girar. Esticar. Afinar a ponta. Mover. Mesmos passos, mesma ordem.'],
 ['Promessa ao cliente','Marque o seu dia. Se quiser, compartilhe só a data da promessa no mural.','promise','Prometeu. Agora tem alguém te esperando. Com cliente esperando, a gente dá um jeito de aparecer.'],
 ['Seu primeiro dia está feito','Guarde sua prática e conclua a aula quando terminar.','finish','Amanhã essa orelha vira o item completo. E eu te mostro o botão que faz metade do trabalho sozinho. Te vejo no Dia 2.']
];
const feedback=text=>{$('feedback')?.replaceChildren(document.createTextNode(text));root.querySelector('.d1-feedback').textContent=text;};
function dateText(iso){return new Date(iso+'T12:00:00').toLocaleDateString('pt-BR',{weekday:'long',day:'numeric',month:'long'});}
function renderMural(){const entries=[];if(state.mural&&state.promessa)entries.push('Sua promessa: entrega até '+dateText(state.prazo||config.prazo)+'.');for(const item of config.mural)entries.push('Uma pessoa marcou sua entrega para '+dateText(item.prazo)+'.');if(!entries.length)entries.push('Ainda não há promessas compartilhadas. Você pode marcar a primeira.');$('mural').replaceChildren(...entries.map(text=>{const p=document.createElement('p');p.textContent=text;return p;}));}
function ready(){const o=state.objeto;return [true,state.copiado&&state.traduzido,state.enviado,state.enviado,state.acoes.includes('girar'),o.altura>1&&state.acoes.includes('esticar'),o.ponta<.5&&state.acoes.includes('afinar'),o.x<-.4&&state.acoes.includes('mover'),state.acoes.includes('olhar'),true,state.promessa,true][state.etapa];}
function touch(save=true){dirty=true;update();if(save){clearTimeout(timer);timer=setTimeout(()=>saveState().catch(()=>{}),600);}}
function action(a){if(a==='girar'&&state.etapa===8)a='olhar';if(!state.acoes.includes(a))state.acoes.push(a);touch();}
async function post(url,data){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(data),credentials:'same-origin'});let out;try{out=await r.json();}catch{throw new Error('Não foi possível guardar agora. Tente novamente.');}if(!r.ok){if(r.status===409)conflict=true;throw new Error(out.erro||'Tente novamente.');}return out;}
async function saveState(concluir=false){
 clearTimeout(timer);if(conflict)throw new Error('Reabra a aula: há uma versão salva em outra aba.');
 while(saving){await saving;}if(!dirty&&!concluir)return;
 if(!dirty&&!concluir)return;
 const snapshot=structuredClone(state);dirty=false;$('save-now').disabled=true;root.querySelector('.d1-save').textContent='Guardando na sua conta…';
 saving=post(config.salvar,{estado:snapshot,revisao:revision,concluir}).then(out=>{revision=out.revisao;state.revisao=revision;state.prazo=out.prazo;if(out.concluida)finished=true;root.querySelector('.d1-save').textContent='Salvo na sua conta. Você pode sair e voltar.';}).catch(e=>{dirty=true;root.querySelector('.d1-save').textContent=e.message+' Suas alterações continuam nesta tela.';throw e;}).finally(()=>{saving=null;$('save-now').disabled=false;});
 await saving;if(dirty&&!conflict){clearTimeout(timer);timer=setTimeout(()=>saveState().catch(()=>{}),600);}
}
function update(){
 const translated=Boolean(state.ingles.trim()&&state.resposta.trim());
 $('next').disabled=!ready();$('back').disabled=state.etapa===0;$('next').hidden=state.etapa===11||(state.etapa===2&&!state.enviado);
 $('undo').disabled=state.historico.length===0;$('send').disabled=!translated||!state.traduzido||state.enviado||sending||translating;
 $('translate-response').disabled=!state.resposta.trim()||translating||sending;
 $('translate-response').textContent=translating?'Traduzindo…':translated?'Traduzir novamente':'Traduzir minha resposta';
 $('translate-response').classList.toggle('d1-secondary',translated);
 $('preview').hidden=!translated;$('en').textContent=state.ingles;
 $('reply').hidden=state.etapa!==2||state.enviado||!state.traduzido;$('pt-result').hidden=!state.traduzido;
 $('translate-request').hidden=state.traduzido;
 $('price-summary').textContent=state.preco?'US$ '+state.preco:'não informado';
 $('next').textContent=state.etapa===1?'Responder ao Alex →':state.etapa===2?'Ver pedido confirmado →':state.etapa===3?'Começar a modelar →':'Continuar →';
 $('sent').hidden=!state.enviado;$('my-message').textContent=state.ingles;
 $('price-confirmed').textContent=state.enviado&&state.preco?'Preço combinado: US$ '+state.preco+' · somente na simulação.':'';
 $('object-info').textContent=referenceMode?'Modelo completo · referência':(state.objeto.ponta<.5?'Orelha selecionada':'Cubo selecionado')+' · '+(state.objeto.x<-.4?'lado esquerdo':'centro');
 $('promise-status').textContent=state.promessa?'Dia marcado. Sua promessa está guardada'+(state.mural?' e sua data participa do mural.':'.'):'';
 $('complete').disabled=finished;$('complete-status').textContent=finished?'Sua aula está concluída. Você pode voltar à prática sempre que quiser.':'';
 const regular=document.querySelector('#concluir button[type=submit]');if(regular&&!config.legado){regular.disabled=!finished;regular.title='Conclua a prática acima para registrar esta aula.';}
 const summary='Primeira orelha à esquerda do fone colorido. Promessa para '+dateText(state.prazo||config.prazo)+'.'+(state.preco?' Preço fictício combinado: US$ '+state.preco+'.':'');$('summary').textContent=summary;
 if(engine&&tool!=='girar'){const k=tool==='esticar'?'altura':tool==='afinar'?'ponta':'x';$('range').value=state.objeto[k];}
}
function selectTool(t){referenceMode=false;root.querySelector('.d1-adjust').hidden=false;$('reference-model').textContent='Ver fone completo';$('reference-model').setAttribute('aria-pressed','false');$('viewport-caption').textContent='Sua prática · modele a primeira orelha';tool=t;root.querySelectorAll('[data-tool]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tool===t)));engine?.setTool(t);
 const labels={girar:['Girar a vista','Arraste em volta do objeto. As formas não mudam.','Arraste para olhar de cima e dos lados. Também pode usar os botões Girar ← e Girar →.'],esticar:['Altura','Arraste o cubo para cima. O controle Altura também estica a forma.','Estique até a altura superar a largura. Não há uma medida exata.'],afinar:['Largura da ponta','Arraste a ponta superior para a esquerda, para dentro.','A base mantém a largura. Os vértices de cima se aproximam, formando a ponta. O interior amarelo aparece na orelha.'],mover:['Posição à esquerda / direita','Na vista de frente, arraste o objeto para a esquerda e para baixo, até tocar o arco do fone.','A esquerda é a da vista de frente. Para comparar com a referência, use Vista de frente. O controle de posição também move a peça.']};
 $('range-label').textContent=labels[t][0];$('tool-hint').textContent=labels[t][1];$('help-text').textContent=labels[t][2];$('range').hidden=t==='girar';$('range-label').hidden=t==='girar';
 $('range').min=t==='esticar'?.5:t==='afinar'?.03:-2.5;$('range').max=t==='esticar'?3:t==='afinar'?1.5:2.5;
 $('less').textContent=t==='girar'?'Girar ←':t==='mover'?'Mover à esquerda':'Diminuir';$('more').textContent=t==='girar'?'Girar →':t==='mover'?'Mover à direita':'Aumentar';update();
}
function show(focus=false){
 const [title,instruction,panel,fala]=steps[state.etapa];
 $('title').textContent=title;$('instruction').textContent=instruction;$('fala').textContent='“'+fala+'”';$('counter').textContent=(state.etapa+1)+' de 12';$('progress').value=state.etapa;
 root.querySelectorAll('[data-d1-panel]').forEach(p=>p.hidden=p.dataset.d1Panel!==panel&&!(panel==='finish'&&p.dataset.d1Panel==='model'));
 $('response').value=state.resposta;$('price').value=state.preco;
 $('original').open=!state.traduzido;$('order').hidden=state.etapa===3;
 $('pt').textContent=state.traduzido?config.pedido_pt:'';
 $('public').checked=state.mural;$('promise-text').textContent='Eu entrego o fone com orelhas de gato do Alex até '+dateText(state.prazo||config.prazo)+'.';renderMural();
 $('request-status').textContent='';$('reply-status').textContent='';feedback('');
 if(panel==='model'||panel==='finish'){
  if(!engine){try{engine=criar(root.querySelector('.d1-viewport'),state,touch,action);}catch{feedback('A vista 3D não abriu neste navegador. Guarde o andamento e tente com a aceleração gráfica ativada.');}}
  selectTool(({4:'girar',5:'esticar',6:'afinar',7:'mover',8:'girar'})[state.etapa]||'girar');engine?.show();
 }
 update();if(focus)$('title').focus();
}
function undo(){const o=state.historico.pop();if(!o)return;state.objeto=o;engine?.aplicar(o);touch();feedback('Alteração desfeita. A conversa e a promessa continuam guardadas.');}
function changeObject(key,value){state.historico.push(structuredClone(state.objeto));state.historico=state.historico.slice(-30);state.objeto[key]=value;if(tool==='mover')state.objeto.y=Math.sqrt(Math.max(.09,2.25-value*value));engine?.aplicar(state.objeto);action(tool);}
root.querySelectorAll('[data-tool]').forEach(b=>b.onclick=()=>selectTool(b.dataset.tool));
$('undo').onclick=()=>{selectTool(tool);undo();};$('front').onclick=()=>engine?.front();$('select').onclick=()=>{selectTool(tool);engine?.select();};
$('reference-model').onclick=()=>{if(!engine)return;referenceMode=!referenceMode;engine.setReference(referenceMode);root.querySelector('.d1-adjust').hidden=referenceMode;$('reference-model').textContent=referenceMode?'Voltar à minha orelha':'Ver fone completo';$('reference-model').setAttribute('aria-pressed',String(referenceMode));$('viewport-caption').textContent=referenceMode?'Referência 3D · fone completo':'Sua prática · modele a primeira orelha';update();};
let rangeStart=null;$('range').addEventListener('pointerdown',()=>rangeStart=structuredClone(state.objeto));
$('range').oninput=()=>{const k=tool==='esticar'?'altura':tool==='afinar'?'ponta':'x';if(rangeStart){state.objeto[k]=Number($('range').value);if(tool==='mover')state.objeto.y=Math.sqrt(Math.max(.09,2.25-state.objeto.x**2));engine?.aplicar(state.objeto);touch(false);}else changeObject(k,Number($('range').value));};
$('range').onchange=()=>{if(rangeStart){state.historico.push(rangeStart);state.historico=state.historico.slice(-30);rangeStart=null;action(tool);}};
for(const [id,sign] of [['less',-1],['more',1]])$(id).onclick=()=>{if(tool==='girar'){engine?.rotate(sign*.4);return;}const key=tool==='esticar'?'altura':tool==='afinar'?'ponta':'x',lo=Number($('range').min),hi=Number($('range').max);changeObject(key,Math.max(lo,Math.min(hi,state.objeto[key]+sign*.15)));};
root.querySelector('.d1-viewport').addEventListener('keydown',e=>{if(e.ctrlKey&&e.key.toLowerCase()==='z'){e.preventDefault();undo();}if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();$(e.key==='ArrowLeft'?'less':'more').click();}});
$('translate-request').onclick=async()=>{const b=$('translate-request');b.disabled=true;b.textContent='Traduzindo…';$('request-status').textContent='';try{const out=await post(config.tradutor,{texto:config.pedido,direcao:'pt'});state.entrada=config.pedido;state.copiado=true;state.traduzido=true;$('pt').textContent=out.texto;$('original').open=false;touch();$('request-status').textContent='Pedido entendido. Agora você pode responder ao Alex.';}catch(e){$('request-status').textContent=e.message;}finally{b.disabled=false;b.textContent='Traduzir pedido para português';}};
function editReply(){state.resposta=$('response').value;state.preco=$('price').value;state.ingles='';state.enviado=false;$('reply-status').textContent='';touch();}
$('response').oninput=editReply;$('price').oninput=editReply;
$('example').onclick=()=>{$('response').value=config.exemplo;editReply();};
$('edit').onclick=()=>{state.etapa=2;state.enviado=false;touch();show(true);};
$('translate-response').onclick=async()=>{if(!state.resposta.trim()||translating)return;const response=state.resposta,price=state.preco;translating=true;update();$('reply-status').textContent='';try{const proposal=response+(price?' O preço é US$ '+price+'.':'');const out=await post(config.tradutor,{texto:proposal,direcao:'en'});if(state.resposta!==response||state.preco!==price){$('reply-status').textContent='Você mudou a resposta. Traduza a nova versão antes de enviar.';return;}state.ingles=out.texto;touch();$('reply-status').textContent='Tradução pronta. Confira a mensagem abaixo e envie quando estiver pronto.';}catch(e){$('reply-status').textContent=e.message;}finally{translating=false;update();}};
$('send').onclick=async()=>{if(!state.ingles||!state.resposta.trim()||!state.traduzido||sending||translating)return;sending=true;state.enviado=true;const previous=state.etapa;state.etapa=3;touch(false);try{await saveState();show(true);}catch(e){state.enviado=false;state.etapa=previous;dirty=true;$('reply-status').textContent=e.message;}finally{sending=false;update();}};
$('promise').onclick=async()=>{state.promessa=true;state.mural=$('public').checked;touch(false);try{await saveState();update();renderMural();feedback('Sua promessa foi registrada.');}catch(e){feedback(e.message);}};
$('complete').onclick=async()=>{try{touch(false);await saveState(true);update();feedback('Prática concluída. Seu pedido, orelha e promessa estão guardados.');location.reload();}catch(e){feedback(e.message);}};
$('save-now').onclick=()=>{dirty=true;saveState().catch(e=>feedback(e.message));};
$('next').onclick=async()=>{if(!ready()||state.etapa>=11)return;const previous=state.etapa;state.etapa++;touch(false);try{await saveState();show(true);}catch(e){state.etapa=previous;feedback(e.message);update();}};
$('back').onclick=()=>{if(state.etapa>0){state.etapa--;touch();show(true);}};$('review-model').onclick=()=>{state.etapa=8;touch();show(true);};
$('watch').onclick=()=>{$('video').currentTime=0;$('video').play().catch(()=>{$('video-status').textContent='Use o botão de reprodução do vídeo para assistir à aula completa.';});};
function restoreVideo(){const video=$('video');video.currentTime=Math.min(resumeVideo,Math.max(0,video.duration-.1));}
if($('video').readyState>=1)restoreVideo();else $('video').addEventListener('loadedmetadata',restoreVideo,{once:true});
for(const event of ['pause','seeked','ended'])$('video').addEventListener(event,()=>{if($('video').readyState>=1){state.video=$('video').currentTime;videoCheckpoint=state.video;touch();}});
$('video').addEventListener('timeupdate',()=>{state.video=$('video').currentTime;dirty=true;if(Math.abs(state.video-videoCheckpoint)>=15){videoCheckpoint=state.video;touch();}});
window.addEventListener('pagehide',()=>{if(!dirty||conflict)return;fetch(config.salvar,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({estado:state,revisao:revision}),credentials:'same-origin',keepalive:true}).catch(()=>{});});
document.addEventListener('visibilitychange',()=>{if(document.hidden&&dirty)saveState().catch(()=>{});});
show();if(revision>0)root.querySelector('.d1-save').textContent='Andamento retomado da sua conta.';
