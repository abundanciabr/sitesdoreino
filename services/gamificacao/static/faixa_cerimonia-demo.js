'use strict';
document.querySelector('#ver-cerimonia').addEventListener('click', () => {
  const ordem = Number(document.querySelector('#faixa-demo').value);
  const nomes = ['Branca','Amarela','Azul','Vermelha','Verde','Marrom','Preta · Grau I','Preta · Grau II','Preta · Grau III','Preta · Grau IV','Preta · Grau V','Preta · Grau VI','Preta · Grau VII'];
  const pontos = [0,5000,10000,15000,20000,25000,30000,40000,50000,75000,100000,150000,200000];
  const data = {pessoa_id:'demonstracao',site_id:'demonstracao',atual_ordem:ordem,
    celebracao:{ordem,tipo:ordem>7?'grau':'cor',bonus_xp:pontos[ordem-1]},
    etapas:nomes.map((nome,i)=>({ordem:i+1,nome,alcancada:i<ordem,conquista:'Seu trabalho foi avaliado e reconhecido.'}))};
  window.MeshcraftFaixas.celebrar(data,data,{demonstracao:true,
    tarefa:{titulo:ordem===2?'Compromisso concluído!':'Realização reconhecida!',feedback:ordem===2?'Você assumiu seu próximo passo.':'Você realizou a etapa e sua conquista foi reconhecida.',xp:ordem<=4?100:0}});
});

