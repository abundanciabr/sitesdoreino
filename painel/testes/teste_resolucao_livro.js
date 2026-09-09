"use strict";
const assert = require("assert"), fs = require("fs"), path = require("path"), vm = require("vm");
const logica = require("../logica.js");
const pasta = path.join(__dirname, "../registros");
const contexto = {window: {REGISTROS: []}};
vm.createContext(contexto);
// Livro imutável presente na revisão 50a6668a, antes da reforma e de suas baixas.
fs.readdirSync(pasta).filter(n => n.endsWith(".js") && n.slice(0, 12) <= "20260909-054").sort().forEach(n => {
  vm.runInContext(fs.readFileSync(path.join(pasta, n), "utf8"), contexto, {timeout: 2000});
});
const registros = Array.from(contexto.window.REGISTROS);
const respostas = new Set(registros.map(r => r.responde_a).filter(Boolean));
const antes = registros.filter(r => ["ambar", "vermelho"].includes(r.gravidade) &&
  !["pendencia", "frente", "rumo"].includes(r.tipo) && !respostas.has(r.arquivo));
const depois = logica.problemasAbertos(registros);
const ids = lista => Array.from(lista, r => r.arquivo).sort();
assert(antes.every(r => depois.some(d => d.arquivo === r.arquivo)), "A reforma ocultou um alerta anterior sem resolução");
assert.deepStrictEqual(ids(logica.caixaDeEntrada(registros, new Date()).map(r => r.registro)),
  ids(registros.filter(r => r.precisa_do_dono && !respostas.has(r.arquivo))), "A reforma reabriu decisões legadas");
const divergencias = depois.filter(r => !antes.some(a => a.arquivo === r.arquivo));
assert.deepStrictEqual(ids(divergencias), [
  "20260828-025-o-projeto-esta-aberto-para-qualquer-pessoa-da-internet",
  "20260828-062-o-boletim-mostrava-o-teto-como-se-fosse-o-total",
  "20260830-093-o-alarme-do-projeto-esta-surdo-e-barulhento-ao-mesmo-tempo",
  "20260831-025-a-gamificacao-destravou-e-so-falta-um-passo-seu",
  "20260831-106-a-sua-tela-de-ligar-os-pontos-esta-pronta",
  "20260904-082-falta-ligar-a-tela-ao-motor-das-mensagens",
  "20260907-074-a-chave-da-ia-avisa-se-nao-chegou",
  "20260908-095-escola-gerenciar-cursos-na-ficha-do-aluno"
], "Mudou a comparação com o livro anterior à reforma; confira cada divergência");
const resumo = logica.montarResumo(registros);
assert.deepStrictEqual(ids(logica.problemasAbertos(resumo.registros, resumo.respondidos)), ids(depois), "O resumo alterou as obrigações");
console.log(JSON.stringify({revisao: "50a6668a", registros: registros.length, alertasAntes: antes.length,
  alertasDepois: depois.length, pedidosPreservados: logica.caixaDeEntrada(registros, new Date()).length,
  divergencias: ids(divergencias)}, null, 2));
