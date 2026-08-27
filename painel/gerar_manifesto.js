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
var SAIDA_LIVRO = path.join(AQUI, "livro.js");
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
var fontes = [];
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
  fontes.push({ base: base, codigo: codigo });
  var lista = sandbox.window.REGISTROS || [];
  if (lista.length !== 1) { problemas.push(nome + ": deve empurrar EXATAMENTE 1 registro (empurrou " + lista.length + ")"); return; }
  var r = lista[0];
  if (r.arquivo !== base) problemas.push(nome + ": campo 'arquivo' ('" + r.arquivo + "') difere do nome do arquivo ('" + base + "')");
  registros.push(r);
});

// A MESMA validação da página. Um contrato, dois guardiões, zero divergência.
problemas = problemas.concat(LOGICA.validarRegistros(registros));
if (problemas.length) falha(problemas);

// DOIS arquivos gerados, e não um só, porque respondem perguntas diferentes —
// e é essa diferença que mantém a trava fail-closed viva:
//
//   manifesto.js → a LISTA do que deveria existir (só os nomes).
//   livro.js     → o CONTEÚDO de todos os registros, num arquivo só.
//
// A página compara os dois ao abrir: livro truncado, pela metade ou ausente faz
// a contagem divergir da lista, e a tela vira o aviso vermelho. Um arquivo só
// não teria como detectar a própria falta.
//
// POR QUE O CONTEÚDO VIRA UM ARQUIVO SÓ (o conserto de 27/08/2026):
// até aqui o manifesto fazia `document.write` de UM <script> por registro, e
// abrir o painel disparava um pedido por registro — 86 de uma vez. Na área
// administrativa CADA pedido atravessa a porta, e a porta pergunta à célula de
// identidade quem é você, com 2 segundos de paciência (`services/admin/apps/
// core/porta.py` + `clients.py`). Sob a rajada, parte das perguntas estourava o
// tempo: o registro voltava como página de erro no lugar do JS e o painel — com
// razão — se recusava a abrir ("o manifesto lista 86, mas só 29 carregaram").
// Aconteceu 4 vezes num dia, com número diferente a cada vez, e piorava a cada
// registro novo, porque o número de pedidos É o tamanho do livro. Um pedido no
// lugar de 86 não deixa esse defeito existir.
//
// Isto NÃO é a duplicação que o CLAUDE.md proíbe: livro.js é DERIVADO — gerado,
// nunca escrito à mão, e o `--conferir` da muralha reprova se ele divergir de
// registros/. Mesmo contrato do manifesto.js e do índice das armadilhas. A
// fonte de verdade continua sendo um arquivo por ocorrência.
//
// Determinístico de propósito (sem timestamp): mesmo livro → mesmos arquivos,
// para o --conferir do CI ser um diff honesto e PRs não conflitarem por churn.
var bases = nomes.map(function (n) { return n.slice(0, -3); });

var AVISO = [
  "// =============================================================================",
  "// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.",
  "// Para regenerar: node painel/gerar_manifesto.js",
  "// ============================================================================="
];

var manifestoConteudo = AVISO.concat([
  "// A lista do que DEVE ter carregado. A página confere",
  "// REGISTROS.length === MANIFESTO.length ao abrir.",
  "var MANIFESTO = " + JSON.stringify(bases, null, 2) + ";",
  ""
]).join("\n");

// O BOM de cada fonte cai fora antes de entrar aqui: no começo de um arquivo ele
// é marca de codificação, mas no MEIO de um arquivo concatenado vira caractere
// solto no meio do código — e derrubaria o livro inteiro, não uma entrada.
var livroConteudo = AVISO.concat([
  "// O livro INTEIRO num arquivo só: " + bases.length + " registros, um pedido.",
  "// A fonte de verdade continua em painel/registros/, um arquivo por ocorrência;",
  "// isto aqui é só o empacotamento que a página carrega.",
  ""
]).concat(fontes.map(function (f) {
  var fonte = f.codigo.replace(/^﻿/, "").replace(/\r\n/g, "\n").replace(/\s+$/, "");
  return "// ---- " + f.base + " ----\n" + fonte;
})).join("\n") + "\n";

var ESCRITAS = [
  { nome: "manifesto.js", caminho: SAIDA, conteudo: manifestoConteudo },
  { nome: "livro.js", caminho: SAIDA_LIVRO, conteudo: livroConteudo }
];

// Fins de linha não são conteúdo: num checkout Windows o git converte o gerado
// para CRLF e a comparação byte a byte reprovava com o livro perfeitamente em
// dia (armadilhas/122, descoberto no clone do mantenedor — no CI Linux passava).
// Normalizar os DOIS lados compara o que importa.
function normalizar(texto) { return texto.replace(/\r\n/g, "\n"); }

var modoConferir = process.argv.indexOf("--conferir") !== -1;
if (modoConferir) {
  var pendencias = [];
  ESCRITAS.forEach(function (e) {
    var atual;
    try { atual = fs.readFileSync(e.caminho, "utf8"); }
    catch (err) { pendencias.push(e.nome + " não existe"); return; }
    if (normalizar(atual) !== normalizar(e.conteudo)) {
      pendencias.push(e.nome + " está DESATUALIZADO em relação a registros/");
    }
  });
  if (pendencias.length) {
    console.error("❌ FAIL: o painel gerado não corresponde ao livro de ocorrências:");
    pendencias.forEach(function (m) { console.error("   - " + m); });
    console.error("   Rode: node painel/gerar_manifesto.js  (e commite o resultado)");
    process.exit(1);
  }
  console.log("✅ manifesto e livro em dia — " + registros.length + " registros válidos.");
  process.exit(0);
}

ESCRITAS.forEach(function (e) {
  try { fs.writeFileSync(e.caminho, e.conteudo, "utf8"); }
  catch (err) { erro("não consegui escrever " + e.nome + ": " + err.message); }
});
console.log("✅ manifesto.js e livro.js gerados — " + registros.length +
  " registros válidos, carregados pela página em UM pedido.");
