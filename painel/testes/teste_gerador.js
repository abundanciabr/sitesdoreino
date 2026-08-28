#!/usr/bin/env node
// =============================================================================
// painel/testes/teste_gerador.js — teste-guarda do gerar_manifesto.js.
//
// Prova os três estados do portão (RETROSPECTIVA-FASE-D §1): aceita o certo,
// RECUSA o errado dizendo o quê, e instrumento quebrado vira ERROR — nunca um
// verde silencioso. Roda o gerador de verdade, num diretório temporário, como
// processo separado (o mesmo jeito que o CI o rodará).
//
// A propriedade que este arquivo existe para fixar, desde 27/08/2026: **abrir o
// painel custa UM pedido, e esse custo não cresce com o tamanho do livro.**
// Não é uma implementação que está travada aqui — é essa frase.
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

// Monta um painel/ de mentira num tmp, com a logica.js e o template REAIS — a
// validação e as regras são as mesmas que rodam em produção.
function montarCenario(registros, opcoes) {
  opcoes = opcoes || {};
  var dir = fs.mkdtempSync(path.join(os.tmpdir(), "painel-teste-"));
  var logica = fs.readFileSync(path.join(RAIZ_PAINEL, "logica.js"), "utf8");
  if (opcoes.orcamentoResumo) {
    logica = logica.replace(/var ORCAMENTO_RESUMO_BYTES = [^;]+;/,
      "var ORCAMENTO_RESUMO_BYTES = " + opcoes.orcamentoResumo + ";");
  }
  fs.writeFileSync(path.join(dir, "logica.js"), logica, "utf8");
  fs.copyFileSync(path.join(RAIZ_PAINEL, "gerar_manifesto.js"), path.join(dir, "gerar_manifesto.js"));
  if (!opcoes.semTemplate) {
    var tpl = fs.readFileSync(path.join(RAIZ_PAINEL, "painel.template.html"), "utf8");
    if (opcoes.templateSemMarcador) tpl = tpl.replace("__DADOS_DO_PAINEL__", "");
    fs.writeFileSync(path.join(dir, "painel.template.html"), tpl, "utf8");
  }
  fs.mkdirSync(path.join(dir, "registros"));
  Object.keys(registros).forEach(function (nome) {
    fs.writeFileSync(path.join(dir, "registros", nome), registros[nome], "utf8");
  });
  return dir;
}
function roda(dir, args) {
  var r = cp.spawnSync(process.execPath, [path.join(dir, "gerar_manifesto.js")].concat(args || []),
    { encoding: "utf8", timeout: 60000 });
  return { code: r.status, out: (r.stdout || "") + (r.stderr || "") };
}
function leia(dir, nome) { return fs.readFileSync(path.join(dir, nome), "utf8"); }
function existe(dir, nome) { return fs.existsSync(path.join(dir, nome)); }

function registroBom(base, extra) {
  var campos = {
    arquivo: base, tipo: "nota", quando: "2026-08-26", titulo: "t", detalhe: "d",
    autoridade: "sessao", evidencia: null, verificado_em: null,
    precisa_do_dono: false, responde_a: null, gravidade: "info",
    frente: null, vence_em_dias: null
  };
  Object.keys(extra || {}).forEach(function (k) { campos[k] = extra[k]; });
  return "(function(){ (window.REGISTROS = window.REGISTROS || []).push(" +
    JSON.stringify(campos) + ");})();";
}

console.log("== o caminho verde ==");
var dir1 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
var r1 = roda(dir1);
caso("livro válido gera o painel (exit 0)", r1.code === 0);
caso("painel.html existe e traz o resumo embutido",
  existe(dir1, "painel.html") && leia(dir1, "painel.html").indexOf("var PAINEL = {") !== -1);
caso("painel.html traz as REGRAS embutidas (a lógica deixou de ser um pedido)",
  leia(dir1, "painel.html").indexOf("montarResumo") !== -1);
caso("--conferir com o painel em dia passa (exit 0)", roda(dir1, ["--conferir"]).code === 0);
caso("o passado vira um arquivo POR MÊS, com o conteúdo",
  existe(dir1, "livro-202608.js") && leia(dir1, "livro-202608.js").indexOf("window.LIVRO") !== -1);
caso("o mês empacotado usa JSON.parse, e não concatenação do fonte (uma aspa errada não derruba o mês inteiro)",
  leia(dir1, "livro-202608.js").indexOf("JSON.parse(") !== -1);

// -----------------------------------------------------------------------------
// A PROPRIEDADE QUE IMPORTA, e a única que vale travar: abrir o painel é UM
// pedido, com 1 registro ou com 1.000. O incidente de 27/08/2026 nasceu de o
// custo de abrir SER o tamanho do livro — 86 pedidos numa rajada, cada um
// atravessando a porta da área administrativa. Isto aqui é a medida, não a
// promessa.
// -----------------------------------------------------------------------------
console.log("== o custo de abrir NÃO cresce com o livro ==");
function pedidosDaAbertura(html) {
  var re = /<script[^>]*\bsrc=["']([^"']+)["']/gi, achados = [], m;
  while ((m = re.exec(html))) achados.push(m[1]);
  return achados;
}
function cenarioComN(n, opcoes) {
  var regs = {};
  for (var i = 1; i <= n; i++) {
    var num = ("00" + (i % 1000)).slice(-3);
    var dia = ("0" + (1 + Math.floor(i / 1000))).slice(-2);
    var base = "202608" + dia + "-" + num + "-r" + i;
    regs[base + ".js"] = registroBom(base, { quando: "2026-08-" + dia });
  }
  return montarCenario(regs, opcoes);
}
[1, 100, 1000].forEach(function (n) {
  var d = cenarioComN(n);
  var r = roda(d);
  var html = r.code === 0 ? leia(d, "painel.html") : "";
  var pedidos = pedidosDaAbertura(html);
  caso("com " + n + " registro(s): gera (exit 0)", r.code === 0);
  caso("com " + n + " registro(s): abrir o painel não busca NENHUM sub-arquivo", pedidos.length === 0);
  caso("com " + n + " registro(s): não voltou a pedir registro por registro",
    pedidos.filter(function (p) { return p.indexOf("registros/") === 0; }).length === 0);
});

console.log("== o gerador RECUSA crescer (o teto que segura, em vez da lei escrita) ==");
var dirOrc = cenarioComN(60, { orcamentoResumo: 500 });
var rOrc = roda(dirOrc);
caso("resumo acima do orçamento REPROVA (exit 1)", rOrc.code === 1);
caso("...e diz que foi o orçamento", rOrc.out.indexOf("orçamento") !== -1);
caso("...e NÃO escreve o painel", !existe(dirOrc, "painel.html"));

console.log("== a recusa (FAIL, exit 1) ==");
var dir2 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-quebrado.js": "(function(){ ISTO NAO E JS VALIDO"
});
var r2 = roda(dir2);
caso("registro com sintaxe quebrada REPROVA (exit 1)", r2.code === 1);
caso("...e diz QUAL arquivo", r2.out.indexOf("20260826-002-quebrado") !== -1);
caso("...e NÃO escreve o painel", !existe(dir2, "painel.html"));
caso("...e NÃO escreve o mês", !existe(dir2, "livro-202608.js"));

var dir3 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-b") });
caso("campo 'arquivo' divergente do nome REPROVA", roda(dir3).code === 1);

var dir4 = montarCenario({ "nome-fora-do-padrao.js": registroBom("nome-fora-do-padrao") });
caso("nome fora do padrão AAAAMMDD-NNN-slug REPROVA", roda(dir4).code === 1);

// A trava que mantém os gerados honestos: mexeu à mão ou ficou para trás, reprova.
var dirA = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dirA);
fs.writeFileSync(path.join(dirA, "painel.html"), "<!-- alguem editou a mao -->", "utf8");
var rA = roda(dirA, ["--conferir"]);
caso("painel.html editado à mão REPROVA no --conferir (exit 1)", rA.code === 1);
caso("...e diz que foi o painel.html", rA.out.indexOf("painel.html") !== -1);

var dirB = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dirB);
fs.writeFileSync(path.join(dirB, "livro-202608.js"), "// alguem editou a mao", "utf8");
var rB = roda(dirB, ["--conferir"]);
caso("o mês empacotado adulterado REPROVA no --conferir (exit 1)", rB.code === 1);
caso("...e diz qual mês", rB.out.indexOf("livro-202608.js") !== -1);

var dir5 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dir5);
fs.writeFileSync(path.join(dir5, "registros", "20260826-002-b.js"), registroBom("20260826-002-b"), "utf8");
var r5 = roda(dir5, ["--conferir"]);
caso("registro novo sem regenerar → --conferir REPROVA (a trava do CI)", r5.code === 1);
caso("...mandando rodar o gerador", r5.out.indexOf("gerar_manifesto") !== -1);

// Mês que deixou de existir e ficou no disco é livro fantasma: sai da página e
// continua sendo servido a quem adivinhar o nome.
var dirF = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dirF);
fs.writeFileSync(path.join(dirF, "livro-202512.js"), "// mes que nao existe mais", "utf8");
var rF = roda(dirF, ["--conferir"]);
caso("mês fantasma no disco REPROVA no --conferir (exit 1)", rF.code === 1);
caso("...e nomeia o fantasma", rF.out.indexOf("livro-202512.js") !== -1);
roda(dirF);
caso("...e gerar de novo REMOVE o fantasma", !existe(dirF, "livro-202512.js"));

var dir5b = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dir5b);
var pPath = path.join(dir5b, "painel.html");
fs.writeFileSync(pPath, fs.readFileSync(pPath, "utf8").replace(/\n/g, "\r\n"), "utf8");
caso("gerado convertido para CRLF pelo checkout do Windows → --conferir ainda PASSA (fim de linha não é conteúdo)",
  roda(dir5b, ["--conferir"]).code === 0);

console.log("== instrumento quebrado é ERROR (exit 2), nunca verde ==");
var dir6 = fs.mkdtempSync(path.join(os.tmpdir(), "painel-teste-"));
fs.copyFileSync(path.join(RAIZ_PAINEL, "logica.js"), path.join(dir6, "logica.js"));
fs.copyFileSync(path.join(RAIZ_PAINEL, "gerar_manifesto.js"), path.join(dir6, "gerar_manifesto.js"));
var r6 = roda(dir6); // sem pasta registros/
caso("pasta registros/ ausente é ERROR (exit 2) — não um livro vazio 'válido'", r6.code === 2);
var dir7 = montarCenario({});
caso("zero registros é ERROR (exit 2) — pasta errada, não projeto parado", roda(dir7).code === 2);
var dir8 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") }, { semTemplate: true });
caso("template ausente é ERROR (exit 2)", roda(dir8).code === 2);
var dir9 = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") }, { templateSemMarcador: true });
var r9 = roda(dir9);
caso("template sem o marcador é ERROR (exit 2) — a página nasceria sem dados e sem regras", r9.code === 2);
caso("...e diz qual marcador falta", r9.out.indexOf("__DADOS_DO_PAINEL__") !== -1);


console.log("== mesmo livro, MESMOS BYTES, em qualquer checkout ==");
// O Git entrega o template em CRLF num clone Windows e em LF num runner Linux.
// Sem normalizar, o mesmo livro produzia dois painel.html diferentes — e o
// `--conferir` não acusava, porque normaliza os dois lados antes de comparar.
// A divergência viajava em silêncio; aqui os bytes são comparados crus.
//
// Os dois cenários escrevem o template EXPLICITAMENTE, um em LF e outro em
// CRLF, em vez de confiar no que o checkout deu — senão o teste mediria o
// `core.autocrlf` da máquina em vez do gerador.
var regsIguais = { "20260826-001-a.js": registroBom("20260826-001-a") };
var tplLF = fs.readFileSync(path.join(RAIZ_PAINEL, "painel.template.html"), "utf8")
  .split("\r\n").join("\n");
var dirLF = montarCenario(regsIguais);
var dirCRLF = montarCenario(regsIguais);
fs.writeFileSync(path.join(dirLF, "painel.template.html"), tplLF, "utf8");
fs.writeFileSync(path.join(dirCRLF, "painel.template.html"),
  tplLF.split("\n").join("\r\n"), "utf8");
caso("os dois cenários são mesmo diferentes no disco (senão isto não prova nada)",
  fs.readFileSync(path.join(dirLF, "painel.template.html"), "utf8").indexOf("\r\n") === -1 &&
  fs.readFileSync(path.join(dirCRLF, "painel.template.html"), "utf8").indexOf("\r\n") !== -1);
roda(dirLF);
roda(dirCRLF);
caso("template em LF e em CRLF geram painel.html byte a byte IDÊNTICO",
  Buffer.compare(fs.readFileSync(path.join(dirLF, "painel.html")),
                 fs.readFileSync(path.join(dirCRLF, "painel.html"))) === 0);
caso("...e o gerado não carrega CRLF nenhum",
  fs.readFileSync(path.join(dirCRLF, "painel.html"), "utf8").indexOf("\r\n") === -1);

console.log("");
if (falhas.length) {
  console.error("❌ " + falhas.length + " caso(s) FALHARAM. O gerador NÃO está confiável.");
  process.exit(1);
}
console.log("✅ teste_gerador: todos os casos passaram.");
