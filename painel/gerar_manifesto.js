#!/usr/bin/env node
// =============================================================================
// painel/gerar_manifesto.js — valida o livro de ocorrências e gera manifesto.js
//
// Por que existe: a página abre por file:// e o Chrome não deixa uma página
// local descobrir arquivos sozinha — o manifesto é a lista de <script src> que
// carrega cada registro. Igual ao ci/indice_de_armadilhas.py: fonte pequena por
// entrada, índice gerado, e uma trava que confere que o índice está em dia.
//
// Por que em Node e não Python: a validação é a MESMA logica.js que a página
// usa ao abrir. Um validador só, imposto dos dois lados — dois validadores
// separados divergiriam em silêncio (RETROSPECTIVA-FASE-D §2).
//
// Uso:
//   node painel/gerar_manifesto.js            → valida e (re)escreve manifesto.js
//   node painel/gerar_manifesto.js --conferir → só confere; sai 1 se desatualizado
//
// Estados (RETROSPECTIVA-FASE-D §1 — ERROR nunca vira PASS):
//   exit 0 = OK · exit 1 = FAIL (registro inválido / manifesto desatualizado)
//   exit 2 = ERROR (não consegui medir: arquivo ilegível, pasta ausente…)
// =============================================================================
"use strict";
var fs = require("fs");
var path = require("path");
var vm = require("vm");

var AQUI = __dirname;
var PASTA = path.join(AQUI, "registros");
var SAIDA = path.join(AQUI, "manifesto.js");
var LOGICA = require(path.join(AQUI, "logica.js"));
var PADRAO_NOME = /^\d{8}-\d{3}-[a-z0-9-]+$/;

function erro(msg) { console.error("❌ ERROR gerar_manifesto: " + msg); process.exit(2); }
function falha(msgs) {
  console.error("❌ FAIL gerar_manifesto — o livro de ocorrências está inválido:");
  msgs.forEach(function (m) { console.error("   - " + m); });
  console.error("   Nada foi escrito. Conserte o registro; não contorne.");
  process.exit(1);
}

if (!fs.existsSync(PASTA)) erro("a pasta " + PASTA + " não existe. Isto NÃO é um livro vazio válido.");

var nomes;
try { nomes = fs.readdirSync(PASTA).filter(function (n) { return n.slice(-3) === ".js"; }).sort(); }
catch (e) { erro("não consegui ler a pasta de registros: " + e.message); }

if (nomes.length === 0) erro("zero registros em " + PASTA + " — um livro sem nenhuma ocorrência é sinal de pasta errada, não de projeto parado.");

// Carrega cada registro num sandbox — exatamente como o navegador o carregaria.
var problemas = [];
var registros = [];
nomes.forEach(function (nome) {
  var base = nome.slice(0, -3);
  if (!PADRAO_NOME.test(base)) {
    problemas.push(nome + ": nome fora do padrão AAAAMMDD-NNN-slug.js");
  }
  var codigo;
  try { codigo = fs.readFileSync(path.join(PASTA, nome), "utf8"); }
  catch (e) { erro("não consegui ler " + nome + ": " + e.message); }
  var sandbox = { window: {} };
  try { vm.runInNewContext(codigo, sandbox, { timeout: 1000 }); }
  catch (e) { problemas.push(nome + ": erro de sintaxe/execução — " + e.message); return; }
  var lista = sandbox.window.REGISTROS || [];
  if (lista.length !== 1) { problemas.push(nome + ": deve empurrar EXATAMENTE 1 registro (empurrou " + lista.length + ")"); return; }
  var r = lista[0];
  if (r.arquivo !== base) problemas.push(nome + ": campo 'arquivo' ('" + r.arquivo + "') difere do nome do arquivo ('" + base + "')");
  registros.push(r);
});

// A MESMA validação da página. Um contrato, dois guardiões, zero divergência.
problemas = problemas.concat(LOGICA.validarRegistros(registros));
if (problemas.length) falha(problemas);

// Determinístico de propósito (sem timestamp): mesmo livro → mesmo manifesto,
// para o --conferir do CI ser um diff honesto e PRs não conflitarem por churn.
var linhas = [
  "// =============================================================================",
  "// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.",
  "// Para regenerar: node painel/gerar_manifesto.js",
  "// A página confere REGISTROS.length === MANIFESTO.length ao abrir: registro",
  "// que não carregar é detectado, nunca ignorado (fail-closed).",
  "// =============================================================================",
  "var MANIFESTO = " + JSON.stringify(nomes.map(function (n) { return n.slice(0, -3); }), null, 2) + ";",
  "if (typeof document !== \"undefined\") {",
  "  MANIFESTO.forEach(function (n) {",
  "    document.write('<script src=\"registros/' + n + '.js\"><\\/script>');",
  "  });",
  "}",
  ""
];
var conteudo = linhas.join("\n");

var modoConferir = process.argv.indexOf("--conferir") !== -1;
if (modoConferir) {
  var atual;
  try { atual = fs.readFileSync(SAIDA, "utf8"); }
  catch (e) { console.error("❌ FAIL: manifesto.js não existe. Rode: node painel/gerar_manifesto.js"); process.exit(1); }
  if (atual !== conteudo) {
    console.error("❌ FAIL: manifesto.js está DESATUALIZADO em relação a registros/.");
    console.error("   Rode: node painel/gerar_manifesto.js  (e commite o resultado)");
    process.exit(1);
  }
  console.log("✅ manifesto em dia — " + registros.length + " registros válidos.");
  process.exit(0);
}

try { fs.writeFileSync(SAIDA, conteudo, "utf8"); }
catch (e) { erro("não consegui escrever manifesto.js: " + e.message); }
console.log("✅ manifesto.js gerado — " + registros.length + " registros válidos.");
