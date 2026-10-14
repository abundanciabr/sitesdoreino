'use strict';
// Estado exclusivamente fictício da prévia administrativa; nunca chama APIs.
function inicial(ensaioGrupos=false) {
  return {pessoas:[
    {id:'ana',nome:'Ana · teste',ativa:true}, {id:'bia',nome:'Bia · teste',ativa:true},
    {id:'caio',nome:'Caio · teste',ativa:true}, {id:'sem-grupo',nome:'Aluno sem grupo · teste',ativa:true},
    {id:'inativo',nome:'Matrícula encerrada · teste',ativa:false},
    {id:'escola',nome:'Responsável · teste',equipe:true,ativa:false},
    {id:'visitante',nome:'Visitante · teste',ativa:false,visitante:true}],
    areas:[{id:'duvidas',nome:'Dúvidas gerais',geral:true,ativo:true},{id:'mostre-seu-trabalho',nome:'Mostre seu trabalho',geral:true,ativo:true},{id:'sala-dos-alunos',nome:'Sala dos alunos',geral:true,ativo:true}],
    grupos:ensaioGrupos?[{id:'a',nome:'Grupo A · teste',responsavel:'escola',vagas:2,ativo:true},
      {id:'b',nome:'Grupo B · teste',responsavel:'escola',vagas:2,ativo:true}]:[],
    vinculos:ensaioGrupos?[{pessoa:'ana',grupo:'a',ativo:true},{pessoa:'bia',grupo:'a',ativo:true},{pessoa:'caio',grupo:'b',ativo:true}]:[],
    conversas:ensaioGrupos?[{id:1,grupo:'a',autor:'bia',titulo:'Como conferir as dimensões?',texto:'Estou preparando o corpo no Blender. Onde confiro X, Y e Z? Já procurei no painel lateral.',respostas:[],aceita:null},
      {id:2,grupo:'b',autor:'caio',titulo:'Dúvida exclusiva do grupo B',texto:'Conversa de teste para conferir o isolamento.',respostas:[],aceita:null}]:[
      {id:1,grupo:'duvidas',autor:'bia',titulo:'Como conferir as dimensões?',texto:'Estou preparando o corpo no Blender. Onde confiro X, Y e Z? Já procurei no painel lateral.',respostas:[],aceita:null},
      {id:2,grupo:'mostre-seu-trabalho',autor:'caio',titulo:'Minha primeira criação',texto:'Uma peça de demonstração, para experimentar a navegação da comunidade.',respostas:[],aceita:null}],
    envios:[],rastro:[],sequencia:2};
}
function pessoa(s,id) {const p=s.pessoas.find(p=>p.id===id);if(!p)throw Error('Pessoa inexistente.');return p;}
function grupo(s,id) {const g=[...s.grupos,...s.areas].find(g=>g.id===id);if(!g)throw Error('Área inexistente.');return g;}
function podeLer(s,ator,id) {const p=pessoa(s,ator),g=grupo(s,id);return !!(p.equipe||(g.ativo&&p.ativa&&(g.geral||s.vinculos.some(v=>v.pessoa===ator&&v.grupo===id&&v.ativo))));}
function seusGrupos(s,ator) {return s.grupos.filter(g=>g.ativo&&podeLer(s,ator,g.id));}
function conferir(s,ator,id) {if(!podeLer(s,ator,id))throw Error('Grupo indisponível para este acesso.');}
function escrever(s,ator,id,titulo,texto) {conferir(s,ator,id);if(!titulo.trim()||!texto.trim())throw Error('Escreva o título e a mensagem.');const t={id:++s.sequencia,grupo:id,autor:ator,titulo:titulo.trim(),texto:texto.trim(),respostas:[],aceita:null};s.conversas.push(t);return t;}
function conversa(s,ator,id) {const t=s.conversas.find(t=>t.id===id);if(!t)throw Error('Conversa inexistente.');conferir(s,ator,t.grupo);return t;}
function responder(s,ator,id,texto) {const t=conversa(s,ator,id);if(!texto.trim())throw Error('Escreva sua resposta.');const r={id:++s.sequencia,autor:ator,texto:texto.trim()};t.respostas.push(r);return r;}
function aceitar(s,ator,id,respostaId) {const t=conversa(s,ator,id);if(t.autor!==ator)throw Error('Só quem pediu ajuda marca a solução.');const r=t.respostas.find(r=>r.id===respostaId);if(!r||r.autor===ator)throw Error('Escolha a resposta de um colega.');t.aceita=r.id;return r;}
function ranking(s,ator) {const contagem={};for(const t of s.conversas.filter(t=>podeLer(s,ator,t.grupo))){const r=t.respostas.find(r=>r.id===t.aceita);if(r&&!pessoa(s,r.autor).equipe)contagem[r.autor]=(contagem[r.autor]||0)+1;}return Object.entries(contagem).map(([id,total])=>({id,total})).sort((a,b)=>b.total-a.total||a.id.localeCompare(b.id));}
function enviar(s,ator,descricao) {const p=pessoa(s,ator);if(!p.ativa||p.equipe||p.visitante)throw Error('Uma matrícula ativa é necessária para um novo envio.');if(!descricao.trim())throw Error('Descreva a versão de teste.');const e={id:++s.sequencia,autor:ator,versao:s.envios.filter(e=>e.autor===ator).length+1,descricao:descricao.trim(),estado:'aguardando',feedback:'',reconhecida:false};s.envios.push(e);return e;}
function seusEnvios(s,ator) {const p=pessoa(s,ator);return p.equipe?s.envios:s.envios.filter(e=>e.autor===ator);}
function retorno(s,ator,id,estado,feedback) {if(!pessoa(s,ator).equipe)throw Error('Colegas não assinam laudos.');const e=s.envios.find(e=>e.id===id);if(!e||!['ajustar','concluido'].includes(estado)||!feedback.trim())throw Error('Escolha o resultado e escreva o retorno de teste.');e.estado=estado;e.feedback=feedback.trim();e.reconhecida=estado==='concluido';return e;}
function vincular(s,ator,aluno,id,ativo,motivo) {if(!pessoa(s,ator).equipe)throw Error('Somente a escola organiza os grupos.');if(!motivo.trim())throw Error('Escreva o motivo.');const p=pessoa(s,aluno),g=grupo(s,id);if(p.equipe||p.visitante)throw Error('Escolha um aluno de teste.');const existente=s.vinculos.find(v=>v.pessoa===aluno&&v.grupo===id&&v.ativo);if(ativo){if(!p.ativa||!g.ativo)throw Error('Matrícula e grupo precisam estar ativos.');if(existente)return existente;if(s.vinculos.filter(v=>v.grupo===id&&v.ativo).length>=g.vagas)throw Error('Este grupo está sem vaga.');s.vinculos.push({pessoa:aluno,grupo:id,ativo:true});}else if(existente)existente.ativo=false;s.rastro.push({ator,aluno,grupo:id,ativo,motivo:motivo.trim()});}
const ComunidadePrevia={inicial,pessoa,grupo,podeLer,seusGrupos,escrever,conversa,responder,aceitar,ranking,enviar,seusEnvios,retorno,vincular};
if(typeof module!=='undefined'&&module.exports)module.exports=ComunidadePrevia;
