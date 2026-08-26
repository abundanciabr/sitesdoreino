#!/usr/bin/env node
// =============================================================================
// painel/testes/teste_gerador.js — teste-guarda do gerar_manifesto.js.
//
// Prova os três estados do portão (RETROSPECTIVA-FASE-D §1): aceita o certo,
// RECUSA o errado dizendo o quê, e instrumento quebrado vira ERROR — nunca um
// verde silencioso. Roda o gerador de verdade, num diretório temporário, como
// processo separado (o mesmo jeito que o CI o rodará).
//
// Rodar: node painel/testes/teste_gerador.js   (exit 0 = verde, 1 = vermelho)
// =============================================================================
"use strict";
var fs = require("fs");
var os = require("os");
var path = require("path");
var cp = require("child_process");

var RAIZ_PAINEL = path.join(__dirname, "..");
var falhas = [];
function caso(nome, cond) {
  if (cond) console.log("  PASS " + nome);
  else { console.error("  FAIL " + nome); falhas.push(nome); }
}

// Monta um painel/ de mentira num tmp, com a logica.js REAL (a validação é a mesma).
function montarCenario(registros) {
  var dir = fs.mkdtempSync(path.join(os.tmpdir(), "painel-teste-"));
  fs.copyFileSync(path.join(RAIZ_PAINEL, "logica.js"), path.join(dir, "logica.js"));
  fs.copyFileSync(path.join(RAIZ_PAINEL, "gerar_manifesto.js"), path.join(dir, "gerar_manifesto.js"));
  fs.mkdirSync(path.join(dir, "registros"));
  Object.keys(registros).forEach(function (nome) {
    fs.writeFileSync(path.join(dir, "registros", nome), registros[nome], "utf8");
  });
  return dir;
}
function roda(dir, args) {
  var r = cp.spawnSync(process.execPath, [path.join(dir, "gerar_manifesto.js")].concat(args || []),
    { encoding: "utf8", timeout: 15000 });
  return { code: r.status, out: (r.stdout || "") + (r.stderr || "") };
}
function registroBom(base) {
  return "(function(){ (window.REGISTROS = window.REGISTROS || []).push({" +
    "arquivo: \"" + base + "\", tipo: \"nota\", quando: \"2026-08-26\"," +
    "titulo: \"t\", detalhe: \"d\", autoridade: \"sessao\", evidencia: null," +
    "verificado_em: null, precisa_do_dono: false, responde_a: null," +
    "gravidade: \"info\", frente: null, vence_em_dias: null});})();";
}

console.log("== o caminho verde ==");
var dir1 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
var r1 = roda(dir1);
caso("livro válido gera manifesto (exit 0)", r1.code === 0);
caso("manifesto.js existe e lista o registro",
  fs.existsSync(path.join(dir1, "manifesto.js")) &&
  fs.readFileSync(path.join(dir1, "manifesto.js"), "utf8").indexOf("20260826-001-a") !== -1);
caso("--conferir com manifesto em dia passa (exit 0)", roda(dir1, ["--conferir"]).code === 0);

console.log("== a recusa (FAIL, exit 1) ==");
var dir2 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-quebrado.js": "(function(){ ISTO NAO E JS VALIDO"
});
var r2 = roda(dir2);
caso("registro com sintaxe quebrada REPROVA (exit 1)", r2.code === 1);
caso("...e diz QUAL arquivo", r2.out.indexOf("20260826-002-quebrado") !== -1);
caso("...e NÃO escreve manifesto", !fs.existsSync(path.join(dir2, "manifesto.js")));

var dir3 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-b") // campo 'arquivo' difere do nome
});
caso("campo 'arquivo' divergente do nome REPROVA", roda(dir3).code === 1);

var dir4 = montarCenario({ "nome-fora-do-padrao.js": registroBom("nome-fora-do-padrao") });
caso("nome fora do padrão AAAAMMDD-NNN-slug REPROVA", roda(dir4).code === 1);

var dir5 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dir5); // gera
fs.writeFileSync(path.join(dir5, "registros", "20260826-002-b.js"), registroBom("20260826-002-b"), "utf8");
var r5 = roda(dir5, ["--conferir"]);
caso("registro novo sem regenerar → --conferir REPROVA (a trava do CI)", r5.code === 1);
caso("...mandando rodar o gerador", r5.out.indexOf("gerar_manifesto") !== -1);

console.log("== instrumento quebrado é ERROR (exit 2), nunca verde ==");
var dir6 = fs.mkdtempSync(path.join(os.tmpdir(), "painel-teste-"));
fs.copyFileSync(path.join(RAIZ_PAINEL, "logica.js"), path.join(dir6, "logica.js"));
fs.copyFileSync(path.join(RAIZ_PAINEL, "gerar_manifesto.js"), path.join(dir6, "gerar_manifesto.js"));
var r6 = roda(dir6); // sem pasta registros/
caso("pasta registros/ ausente é ERROR (exit 2) — não um livro vazio 'válido'", r6.code === 2);
var dir7 = montarCenario({});
caso("zero registros é ERROR (exit 2) — pasta errada, não projeto parado", roda(dir7).code === 2);

console.log("");
if (falhas.length) {
  console.error("❌ " + falhas.length + " caso(s) FALHARAM. O gerador NÃO está confiável.");
  process.exit(1);
}
console.log("✅ teste_gerador: todos os casos passaram.");
