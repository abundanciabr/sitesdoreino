'use strict';
// Ensaio administrativo isolado. IDs não são credenciais de acesso ao site.
const PRIMEIROS = ['Lia','Caio','Nina','Theo','Bia','Ravi','Luna','Davi','Maya','Ivo','Clara','Enzo','Júlia','Noah','Lara','Ian','Alice','Otto','Elisa','Gael'];
const SOBRENOMES = ['Monteiro','Campos','Luz','Andrade','Vale','Ramos','Duarte','Moraes','Castro','Farias','Prado','Nunes','Lopes','Vieira','Reis','Mendes','Santos','Azevedo','Costa','Rocha'];
const BIOS = ['Curto criar mundos pequenos e cheios de detalhes.','Explorando cores, formas e personagens em 3D.','Ideias de jogos e modelos low poly.','Meu próximo projeto começa com um cubo.','Aprendendo a dar forma às minhas ideias.'];
const TIPOS = Object.freeze({sintetico:Object.freeze(['curtir','seguir']),utilitario:Object.freeze([])});
function inteiro(v,min,max,nome) { if (!Number.isSafeInteger(v)||v<min||v>max) throw new Error(nome+' inválido.'); }
function criarEstado() { return {versao:1,ambiente:'demonstracao',perfis:[],acoes:[],pausado:false,sequencia:0}; }
function adicionarLote(s,quantidade=20,lote='inicial') {
  inteiro(quantidade,1,100,'Quantidade');
  if (typeof lote!=='string'||!/^[a-z0-9-]{1,50}$/.test(lote)) throw new Error('Lote inválido.');
  const anteriores=s.perfis.filter(p=>p.lote===lote);
  if (anteriores.length) { if (anteriores.length!==quantidade) throw new Error('Lote já existe com outra quantidade.'); return anteriores; }
  const inicio=s.perfis.length;
  const novos=Array.from({length:quantidade},(_,i)=>{const n=inicio+i; return {
    id:`sintetico-${lote}-${String(i+1).padStart(3,'0')}`,lote,tipo:'sintetico',
    nome:`${PRIMEIROS[n%20]} ${SOBRENOMES[(n*7+Math.floor(n/20))%20]}`,usuario:`perfil${String(n+1).padStart(3,'0')}`,
    bio:BIOS[n%BIOS.length],avatar:{estilo:'geometrico',cor:(n*137+210)%360,variante:n%4},ativo:true};});
  s.perfis.push(...novos); return novos;
}
function agendar(s,{tipo,alvo,quantidade,agora,janelaMinutos=60}) {
  if (!TIPOS.sintetico.includes(tipo)) throw new Error('Os perfis fictícios apenas curtem e seguem.');
  if (typeof alvo!=='string'||!/^demo-(post|pessoa)-[1-9][0-9]*$/.test(alvo)) throw new Error('Apenas alvos de demonstração.');
  if ((tipo==='curtir')!==alvo.startsWith('demo-post-')) throw new Error('Tipo de alvo incompatível.');
  inteiro(quantidade,1,100,'Quantidade'); inteiro(agora,0,Number.MAX_SAFE_INTEGER,'Horário'); inteiro(janelaMinutos,1,1440,'Janela');
  if (s.pausado) throw new Error('Retome a simulação para agendar.');
  const candidatos=s.perfis.filter(p=>p.ativo&&p.tipo==='sintetico'&&!s.acoes.some(a=>a.perfilId===p.id&&a.tipo===tipo&&a.alvo===alvo&&a.estado!=='cancelada'));
  const escolhidos=candidatos.slice(0,quantidade);
  const novas=escolhidos.map((p,i)=>({id:`acao-${++s.sequencia}`,perfilId:p.id,tipo,alvo,agendadaPara:agora+Math.ceil((i+1)*janelaMinutos*60000/escolhidos.length),estado:'pendente',executadaEm:null}));
  s.acoes.push(...novas); return novas;
}
function executarVencidas(s,agora,alvos) {
  inteiro(agora,0,Number.MAX_SAFE_INTEGER,'Horário'); if (s.pausado) return 0; let feitas=0;
  for(const a of s.acoes) {
    if(a.estado!=='pendente'||a.agendadaPara>agora) continue;
    const p=s.perfis.find(p=>p.id===a.perfilId);
    if(!p?.ativo||!alvos.includes(a.alvo)){a.estado='cancelada';a.motivo=!p?.ativo?'Perfil pausado':'Alvo indisponível';continue;}
    a.estado='concluida';a.executadaEm=agora;feitas++;
  } return feitas;
}
function pausarPerfil(s,id){const p=s.perfis.find(p=>p.id===id);if(!p)throw new Error('Perfil não encontrado.');p.ativo=!p.ativo;return p.ativo;}
function cancelarPendentes(s){let n=0;for(const a of s.acoes)if(a.estado==='pendente'){a.estado='cancelada';a.motivo='Cancelada no painel';n++;}return n;}
function resumo(s){return {perfis:s.perfis.length,ativos:s.perfis.filter(p=>p.ativo).length,curtidas:s.acoes.filter(a=>a.tipo==='curtir'&&a.estado==='concluida').length,seguidores:s.acoes.filter(a=>a.tipo==='seguir'&&a.estado==='concluida').length,pendentes:s.acoes.filter(a=>a.estado==='pendente').length,canceladas:s.acoes.filter(a=>a.estado==='cancelada').length,alunosReaisCriados:0,vendas:0,xp:0};}
const MotorPerfis={criarEstado,adicionarLote,agendar,executarVencidas,pausarPerfil,cancelarPendentes,resumo,TIPOS};
if(typeof module!=='undefined'&&module.exports)module.exports=MotorPerfis;
