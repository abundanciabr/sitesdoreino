#!/usr/bin/env node
// =============================================================================
// painel/testes/teste_logica.js — o teste-guarda da lógica que calcula o painel.
//
// "Quem vigia o vigia da tela": um erro na lógica esconde problema sem ninguém
// mentir. Cada regra abaixo é testada nos DOIS sentidos — aceita o certo e
// RECUSA o errado (RETROSPECTIVA-FASE-D §1: portão que nunca reprovou é portão
// que ninguém sabe se reprova).
//
// Rodar: node painel/testes/teste_logica.js   (exit 0 = verde, 1 = vermelho)
// =============================================================================
"use strict";
var path = require("path");
var LOGICA = require(path.join(__dirname, "..", "logica.js"));

var falhas = [];
function caso(nome, cond) {
  if (cond) console.log("  PASS " + nome);
  else { console.error("  FAIL " + nome); falhas.push(nome); }
}
function reg(sobre) {
  var base = {
    arquivo: "20260826-900-teste", tipo: "nota", quando: "2026-08-26",
    titulo: "t", detalhe: "d", autoridade: "sessao", evidencia: null,
    verificado_em: null, precisa_do_dono: false, responde_a: null,
    gravidade: "info", frente: null, vence_em_dias: null
  };
  Object.keys(sobre || {}).forEach(function (k) { base[k] = sobre[k]; });
  return base;
}
var AGORA = new Date("2026-08-26T15:00:00");

console.log("== validarRegistros ==");
caso("registro completo passa", LOGICA.validarRegistros([reg({})]).length === 0);
caso("campo obrigatório ausente REPROVA", LOGICA.validarRegistros([reg({ titulo: "" })]).length > 0);
caso("tipo desconhecido REPROVA", LOGICA.validarRegistros([reg({ tipo: "invencao" })]).length > 0);
caso("data inválida REPROVA", LOGICA.validarRegistros([reg({ quando: "ontem" })]).length > 0);
caso("HTML no título REPROVA", LOGICA.validarRegistros([reg({ titulo: "oi <b>x</b>" })]).length > 0);
caso("arquivo duplicado REPROVA",
  LOGICA.validarRegistros([reg({}), reg({})]).length > 0);
caso("responde_a inexistente REPROVA",
  LOGICA.validarRegistros([reg({ responde_a: "20990101-001-fantasma" })]).length > 0);
caso("não-lista vira erro, nunca silêncio", LOGICA.validarRegistros(null).length > 0);

console.log("== verde é conquistado, nunca escrito ==");
caso("verde SEM evidência REPROVA", LOGICA.validarRegistros([reg({ gravidade: "verde" })]).length > 0);
caso("verde com evidência mas SEM verificado_em REPROVA",
  LOGICA.validarRegistros([reg({ gravidade: "verde", evidencia: "x" })]).length > 0);
caso("verde com evidência conferida passa",
  LOGICA.validarRegistros([reg({ gravidade: "verde", evidencia: "x", verificado_em: "2026-08-26" })]).length === 0);

console.log("== a caixa que não consegue esquecer ==");
var pedido = reg({ arquivo: "20260820-001-pedido", tipo: "pendencia", quando: "2026-08-20", precisa_do_dono: true });
caso("pedido sem resposta APARECE na caixa",
  LOGICA.caixaDeEntrada([pedido], AGORA).length === 1);
caso("a idade do pedido é calculada (6 dias)",
  LOGICA.caixaDeEntrada([pedido], AGORA)[0].aguardandoDias === 6);
var resposta = reg({ arquivo: "20260826-002-resposta", tipo: "resposta", responde_a: "20260820-001-pedido" });
caso("pedido RESPONDIDO some da caixa — sem ninguém apagar nada",
  LOGICA.caixaDeEntrada([pedido, resposta], AGORA).length === 0);
var pedidoNovo = reg({ arquivo: "20260825-001-novo", tipo: "pendencia", quando: "2026-08-25", precisa_do_dono: true });
caso("pedido mais VELHO grita primeiro",
  LOGICA.caixaDeEntrada([pedidoNovo, pedido], AGORA)[0].registro.arquivo === "20260820-001-pedido");

console.log("== problemas e mudanças ==");
var incendio = reg({ arquivo: "20260826-003-incendio", tipo: "incidente", gravidade: "vermelho" });
caso("incidente vermelho sem resposta está em 'problemas abertos'",
  LOGICA.problemasAbertos([incendio]).length === 1);
var apagado = reg({ arquivo: "20260826-004-apagado", tipo: "resposta", responde_a: "20260826-003-incendio" });
caso("incidente respondido SAI de problemas abertos",
  LOGICA.problemasAbertos([incendio, apagado]).length === 0);
caso("frente âmbar NÃO vira 'problema aberto' (frente tem bloco próprio — um fato, uma casa)",
  LOGICA.problemasAbertos([reg({ tipo: "frente", frente: "curso", gravidade: "ambar" })]).length === 0);
caso("pendência âmbar NÃO vira 'problema aberto' (pendência mora na caixa)",
  LOGICA.problemasAbertos([reg({ tipo: "pendencia", gravidade: "ambar", precisa_do_dono: true })]).length === 0);
caso("mudança de 3 dias atrás entra nos '7 dias'",
  LOGICA.mudancasRecentes([reg({ quando: "2026-08-23" })], AGORA, 7).length === 1);
caso("mudança de 20 dias atrás NÃO entra",
  LOGICA.mudancasRecentes([reg({ quando: "2026-08-06" })], AGORA, 7).length === 0);

console.log("== frentes: o mais recente vence, nada é mantido ==");
var f1 = reg({ arquivo: "20260820-002-f", tipo: "frente", frente: "site", quando: "2026-08-20", titulo: "antigo" });
var f2 = reg({ arquivo: "20260825-002-f", tipo: "frente", frente: "site", quando: "2026-08-25", titulo: "novo" });
var site = LOGICA.estadoDasFrentes([f1, f2]).filter(function (x) { return x.frente === "site"; })[0];
caso("o estado da frente é o registro mais recente", site.registro.titulo === "novo");
caso("frente sem registro aparece como nula (não some)",
  LOGICA.estadoDasFrentes([f1, f2]).filter(function (x) { return x.registro === null; }).length === 4);
caso("tipo 'frente' sem frente válida REPROVA",
  LOGICA.validarRegistros([reg({ tipo: "frente", frente: "outra" })]).length > 0);

console.log("== frescor computado ==");
var vencido = reg({ arquivo: "20260810-001-v", quando: "2026-08-10", vence_em_dias: 7 });
caso("registro vencido é DENUNCIADO", LOGICA.frescor([vencido], AGORA).vencidos.length === 1);
caso("registro dentro do prazo não é",
  LOGICA.frescor([reg({ quando: "2026-08-24", vence_em_dias: 7 })], AGORA).vencidos.length === 0);
caso("o livro parado há N dias é medido",
  LOGICA.frescor([reg({ quando: "2026-08-20" })], AGORA).livroParadoHaDias === 6);

console.log("== dito, mas não comprovado ==");
caso("entrega sem evidência conferida é marcada",
  LOGICA.naoComprovados([reg({ tipo: "entrega" })]).length === 1);
caso("entrega com evidência conferida NÃO é",
  LOGICA.naoComprovados([reg({ tipo: "entrega", evidencia: "x", verificado_em: "2026-08-26" })]).length === 0);

console.log("== a capa: calculada e com teto ==");
var capaOk = LOGICA.capa([pedido, incendio, f1], AGORA);
caso("capa normal constrói sem erro", capaOk.erro === null && capaOk.blocos.length >= 3);
caso("o bloco 'Precisa de você' vem PRIMEIRO (caixa antes do placar)",
  capaOk.blocos[0].id === "caixa");
// Vermelho→verde do teto: o cenário cheio gera os 6 blocos possíveis e AINDA
// constrói; o MESMO cenário com o teto apertado tem que RECUSAR — prova de que
// a recusa dispara de verdade, não é código morto.
var regsCheios = [pedido, incendio, vencido, reg({ tipo: "entrega", arquivo: "20260826-005-e" }), f1];
var capaCheia = LOGICA.capa(regsCheios, AGORA);
caso("cenário cheio usa os 6 blocos e ainda constrói (teto real = " + LOGICA.TETO_BLOCOS_CAPA + ")",
  capaCheia.erro === null && capaCheia.blocos.length === 6);
var capaRecusada = LOGICA._capaComTeto(regsCheios, AGORA, 2);
caso("acima do teto a capa se RECUSA a construir e diz o porquê",
  capaRecusada.erro !== null && capaRecusada.blocos === null && capaRecusada.erro.indexOf("teto") !== -1);

console.log("");
if (falhas.length) {
  console.error("❌ " + falhas.length + " caso(s) FALHARAM. A lógica do painel NÃO está confiável.");
  process.exit(1);
}
console.log("✅ teste_logica: todos os casos passaram.");
