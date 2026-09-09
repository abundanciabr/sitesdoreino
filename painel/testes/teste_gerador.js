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
  // Injeta uma linha ANTES da IIFE que abre o arquivo, sem mexer no logica.js
  // real — só para o teste do TAR-274 provar que um "//" no MEIO de uma linha
  // (uma URL numa string) sobrevive à limpeza.
  if (opcoes.logicaExtra) logica = opcoes.logicaExtra + "\n" + logica;
  fs.writeFileSync(path.join(dir, "logica.js"), logica, "utf8");
  fs.copyFileSync(path.join(RAIZ_PAINEL, "gerar_manifesto.js"), path.join(dir, "gerar_manifesto.js"));
  if (!opcoes.semTemplate) {
    var tpl = fs.readFileSync(path.join(RAIZ_PAINEL, "painel.template.html"), "utf8");
    if (opcoes.templateSemMarcador) tpl = tpl.replace("__DADOS_DO_PAINEL__", "");
    fs.writeFileSync(path.join(dir, "painel.template.html"), tpl, "utf8");
  }
  // As áreas do site viajam com o cenário porque o gerador é fail-closed sem
  // elas. `areas` troca o conteúdo (para o cenário do arquivo inválido) e
  // `semAreas` não escreve o arquivo nenhum.
  if (!opcoes.semAreas) {
    fs.writeFileSync(path.join(dir, "areas.json"),
      opcoes.areas !== undefined ? opcoes.areas
        : fs.readFileSync(path.join(RAIZ_PAINEL, "areas.json"), "utf8"), "utf8");
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

function camposDoRegistro(base, extra) {
  var campos = {
    arquivo: base, tipo: "nota", quando: "2026-08-26", titulo: "t", detalhe: "d",
    autoridade: "sessao", evidencia: null, verificado_em: null,
    precisa_do_dono: false, responde_a: null, gravidade: "info",
    frente: null, vence_em_dias: null
  };
  Object.keys(extra || {}).forEach(function (k) { campos[k] = extra[k]; });
  return campos;
}
function registroBom(base, extra) {
  return "(function(){ (window.REGISTROS = window.REGISTROS || []).push(" +
    JSON.stringify(camposDoRegistro(base, extra)) + ");})();";
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

// UMA LINHA POR REGISTRO (Onda 3, P15/O18). A propriedade é de FORMA, e por
// isso precisa de guarda: nada quebra visivelmente se ela se perder — o painel
// continua abrindo igual, e só quem for comparar duas gerações descobre que
// passou a ler um bloco inteiro trocado no lugar de uma linha a mais. Medido
// contando as linhas, nunca procurando uma quebra de linha no texto: um
// arquivo com tudo numa linha só também contém "JSON.parse(".
var dirLinhas = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-b.js": registroBom("20260826-002-b"),
  "20260826-003-c.js": registroBom("20260826-003-c")
});
roda(dirLinhas);
var linhasDoMes = leia(dirLinhas, "livro-202608.js")
  .split(String.fromCharCode(10))
  .filter(function (ln) { return ln.indexOf("JSON.parse(") === 0; });
caso("cada registro do mês ocupa UMA linha própria (3 registros = 3 linhas)",
  linhasDoMes.length === 3);
caso("...as linhas do meio levam vírgula",
  linhasDoMes[0].slice(-2) === "),");
caso("...e a última não leva vírgula pendurada",
  linhasDoMes[2].slice(-1) === ")");

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


console.log("== o carimbo da geração ==");
// A página e cada arquivo de mês carregam a impressão digital do livro que os
// produziu. É ela que separa "o arquivo não chegou" de "os arquivos são de
// gerações diferentes" — o caso que o mantenedor tem de sobra, porque o
// repositório mora dentro do OneDrive e uma sincronização pela metade entrega
// alguns arquivos novos e outros velhos, cada um íntegro por si.
function carimboDe(texto) {
  var m = /carimbo: "([a-f0-9]+)"/.exec(texto);
  return m ? m[1] : null;
}
var dirC = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-b.js": registroBom("20260826-002-b")
});
roda(dirC);
var carimboPagina = carimboDe(leia(dirC, "painel.html"));
var carimboMes = carimboDe(leia(dirC, "livro-202608.js"));
caso("a página carrega um carimbo", !!carimboPagina);
caso("o arquivo do mês carrega o MESMO carimbo", carimboMes === carimboPagina);

// Determinismo: sem isto, dois checkouts do mesmo commit gerariam carimbos
// diferentes e a comparação viraria alarme falso permanente.
var dirC2 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-b.js": registroBom("20260826-002-b")
});
roda(dirC2);
caso("mesmo livro → MESMO carimbo (sem relógio, sem número de build)",
  carimboDe(leia(dirC2, "painel.html")) === carimboPagina);

// E o contrário, que é o que faz o carimbo valer alguma coisa: livro diferente
// tem de dar carimbo diferente. Um carimbo que nunca muda é decoração.
var dirC3 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a", { titulo: "outro titulo" }),
  "20260826-002-b.js": registroBom("20260826-002-b")
});
roda(dirC3);
caso("livro diferente → carimbo DIFERENTE (senão ele não detecta nada)",
  carimboDe(leia(dirC3, "painel.html")) !== carimboPagina);

// Fim de linha não é conteúdo: um checkout Windows e um runner Linux têm de
// produzir o mesmo carimbo, senão o painel acusaria "gerações diferentes"
// toda vez que o dono abrisse o arquivo do PC dele.
var dirC4 = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a").split("\n").join("\r\n"),
  "20260826-002-b.js": registroBom("20260826-002-b").split("\n").join("\r\n")
});
roda(dirC4);
caso("registro em CRLF → MESMO carimbo (fim de linha não é conteúdo)",
  carimboDe(leia(dirC4, "painel.html")) === carimboPagina);

console.log("== as três ilhas de script da página compilam ==");
// O mais perto que dá para chegar de "a página vai rodar" sem um navegador: as
// ilhas são extraídas com a MESMA regex que o Django usa para calcular o CSP
// (services/admin/apps/core/painel.py) e compiladas. Um erro de sintaxe no
// template passaria por todos os outros testes e só apareceria na tela do dono.
// Quem executa de verdade, com DOM, é o teste de navegador do CI.
var vm = require("vm");
var htmlGerado = leia(dirC, "painel.html");
var reIlha = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
var ilhas = [], achou;
while ((achou = reIlha.exec(htmlGerado))) ilhas.push(achou[1]);
caso("a página tem exatamente 3 ilhas (regras, dados, aplicação)", ilhas.length === 3);
ilhas.forEach(function (codigo, i) {
  var ok = true;
  try { new vm.Script(codigo); } catch (e) { ok = false; console.error("      " + e.message); }
  caso("a ilha " + (i + 1) + " compila como JavaScript válido", ok);
});
// As duas primeiras não dependem de DOM: executam de verdade.
var sandbox = { window: {} };
sandbox.window.window = sandbox.window;
vm.createContext(sandbox);
var executou = true;
try {
  vm.runInContext(ilhas[0], sandbox, { timeout: 5000 });
  vm.runInContext(ilhas[1], sandbox, { timeout: 5000 });
} catch (e) { executou = false; console.error("      " + e.message); }
caso("as ilhas de regras e de dados EXECUTAM", executou);
caso("...e deixam LOGICA e PAINEL de pé",
  executou && typeof sandbox.window.LOGICA === "object" && typeof sandbox.PAINEL === "object");
caso("a página gerada traz a indicação do modelo antes da cópia do prompt",
  htmlGerado.indexOf("modelo-indicado") !== -1 && htmlGerado.indexOf("modeloParaTarefa") !== -1);

// -----------------------------------------------------------------------------
// TAR-274: o bloco embutido das regras (ilhas[0], acima) viaja SEM as linhas de
// comentário — quem lê ali é o navegador, não gente, e cada `//` era peso morto
// contra o orçamento. O arquivo em disco (logica.js) e o que ele CALCULA não
// podem mudar nem uma vírgula: os dois lados têm de ler a MESMA regra.
// -----------------------------------------------------------------------------
console.log("== as regras embutidas viajam SEM os comentários, e continuam a MESMA regra (TAR-274) ==");
caso("nenhuma linha do bloco embutido começa com // (sem os espaços da frente)",
  ilhas[0].split("\n").every(function (l) { return l.trimStart().indexOf("//") !== 0; }));

var logicaDoDisco = require(path.join(RAIZ_PAINEL, "logica.js"));
var LOGICA_EMBUTIDA = sandbox.window.LOGICA;
caso("o LOGICA embutido expõe EXATAMENTE as mesmas chaves da fonte completa",
  !!LOGICA_EMBUTIDA &&
  JSON.stringify(Object.keys(LOGICA_EMBUTIDA).sort()) === JSON.stringify(Object.keys(logicaDoDisco).sort()));

var registrosDoLivro = [camposDoRegistro("20260826-001-a"), camposDoRegistro("20260826-002-b")];
var areasReais = JSON.parse(fs.readFileSync(path.join(RAIZ_PAINEL, "areas.json"), "utf8")).areas;
var agoraFixo = new Date("2026-08-30T12:00:00");
caso("...e prioridades(...) sobre o livro do cenário devolve o MESMO JSON que a cópia completa",
  !!LOGICA_EMBUTIDA &&
  JSON.stringify(logicaDoDisco.prioridades(registrosDoLivro, agoraFixo, undefined, areasReais)) ===
  JSON.stringify(LOGICA_EMBUTIDA.prioridades(registrosDoLivro, agoraFixo, undefined, areasReais)));
caso("...e capa(...) sobre o mesmo livro também devolve o MESMO JSON",
  !!LOGICA_EMBUTIDA &&
  JSON.stringify(logicaDoDisco.capa(registrosDoLivro, agoraFixo)) ===
  JSON.stringify(LOGICA_EMBUTIDA.capa(registrosDoLivro, agoraFixo)));

// Um "//" no MEIO de uma linha (uma URL dentro de uma string) não é comentário
// — só a linha que COMEÇA com "//" sai. painel/logica.js de verdade não tem
// nenhuma linha assim hoje (`grep -n '"[^"]*//' painel/logica.js`), então o
// cenário injeta uma para provar a sobrevivência sem depender disso mudar.
var dirUrl = montarCenario(
  { "20260826-001-a.js": registroBom("20260826-001-a") },
  { logicaExtra: 'var URL_DE_EXEMPLO = "veja https://meshcraft.top/admin para mais.";' }
);
roda(dirUrl);
var ilhasUrl = [], achouUrl;
var reIlhaUrl = /<script(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g;
var htmlUrl = leia(dirUrl, "painel.html");
while ((achouUrl = reIlhaUrl.exec(htmlUrl))) ilhasUrl.push(achouUrl[1]);
caso("uma linha com // NO MEIO (uma URL numa string) sobrevive intacta",
  !!ilhasUrl[0] &&
  ilhasUrl[0].indexOf('var URL_DE_EXEMPLO = "veja https://meshcraft.top/admin para mais.";') !== -1);


console.log("== o painel declara quanto do orçamento ja ocupa ==");
// A faixa que mostra o tanque enchendo só vale se o número for o TAMANHO REAL.
// O gerador carimba um marcador de largura fixa e o troca depois de medir; se
// o número trocado tivesse outra largura, a página declararia um tamanho que
// ela não tem — e a barra mentiria justamente sobre o teto que a protege.
var dirO = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a"),
  "20260826-002-b.js": registroBom("20260826-002-b")
});
roda(dirO);
var htmlO = leia(dirO, "painel.html");
var mO = /paginaBytes: (\d+)/.exec(htmlO);
caso("a página declara o próprio tamanho", !!mO);
caso("...e o número declarado É o tamanho real, byte a byte",
  !!mO && parseInt(mO[1], 10) === Buffer.byteLength(htmlO, "utf8"));
var mR = /resumoBytes: (\d+)/.exec(htmlO);
caso("declara também o tamanho do resumo", !!mR && parseInt(mR[1], 10) > 0);
var mT = /resumoTeto: (\d+)[^}]*paginaTeto: (\d+)/.exec(htmlO);
caso("...e os dois tetos, para a barra ter denominador",
  !!mT && parseInt(mT[1], 10) > 0 && parseInt(mT[2], 10) > 0);
caso("o marcador de largura fixa nao sobrou na pagina",
  htmlO.indexOf("__TAMANHO__") === -1);

// -----------------------------------------------------------------------------
// A FILA DELE, CARIMBADA NA PÁGINA (07/09/2026, degrau 1 da Central de
// Pendências). A área administrativa lê este número de fora, sem executar
// JavaScript, para dizer quantas decisões estão paradas esperando o
// mantenedor. Por isso a propriedade travada aqui não é "o campo existe": é
// que ele CONTA a mesma coisa que a caixa "Precisa de você" da tela dele, e
// que ele REAGE — pedido respondido sai da conta.
//
// Sem o segundo caso, um gerador que carimbasse `quantidade: 0` para sempre
// passaria neste arquivo, e a Central diria "nada esperando você" com a caixa
// dele cheia. É a mentira mais cara que esta tela pode contar.
// -----------------------------------------------------------------------------
console.log("== a página carimba a fila do mantenedor, para quem não roda JavaScript ==");
function filaCarimbada(html) {
  var m = /pedidosDoDono: \{ quantidade: (\d+), maisAntigoQuando: (null|"[^"]*") \}/.exec(html);
  return m ? { quantidade: parseInt(m[1], 10), maisAntigo: JSON.parse(m[2]) } : null;
}

var dirFila = montarCenario({
  "20260826-001-pede.js": registroBom("20260826-001-pede", { precisa_do_dono: true, quando: "2026-08-26" }),
  "20260827-001-pede.js": registroBom("20260827-001-pede", { precisa_do_dono: true, quando: "2026-08-27" }),
  "20260828-001-calado.js": registroBom("20260828-001-calado")
});
roda(dirFila);
var filaDois = filaCarimbada(leia(dirFila, "painel.html"));
caso("a página carimba a fila em forma legível de fora", !!filaDois);
caso("...e conta SÓ os pedidos que precisam dele (2 de 3 registros)",
  !!filaDois && filaDois.quantidade === 2);
caso("...dizendo a data do mais antigo, que é de onde sai 'espera há N dias'",
  !!filaDois && filaDois.maisAntigo === "2026-08-26");

// O MESMO livro, com o pedido mais velho respondido: a conta tem de cair para
// 1 e o mais antigo tem de virar o outro. É a prova de que o número é
// calculado pela regra do painel, e não um contador de campos `true`.
var dirResp = montarCenario({
  "20260826-001-pede.js": registroBom("20260826-001-pede", { precisa_do_dono: true, quando: "2026-08-26" }),
  "20260827-001-pede.js": registroBom("20260827-001-pede", { precisa_do_dono: true, quando: "2026-08-27" }),
  "20260829-001-responde.js": registroBom("20260829-001-responde", { responde_a: "20260826-001-pede" })
});
roda(dirResp);
var filaUm = filaCarimbada(leia(dirResp, "painel.html"));
caso("pedido respondido SAI da conta (2 vira 1)", !!filaUm && filaUm.quantidade === 1);
caso("...e o mais antigo passa a ser o que sobrou",
  !!filaUm && filaUm.maisAntigo === "2026-08-27");

// Livro sem nenhum pedido aberto: zero é um resultado legítimo, e a data é
// nula em vez de uma data inventada.
var dirZero = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dirZero);
var filaZero = filaCarimbada(leia(dirZero, "painel.html"));
caso("livro sem pedido nenhum carimba zero, e não some", !!filaZero && filaZero.quantidade === 0);
caso("...com a data do mais antigo em null, nunca uma data inventada",
  !!filaZero && filaZero.maisAntigo === null);

// ---------------------------------------------------------------------------
// AS ÁREAS DO SITE (07/09/2026, a aba Prioridades). Elas viajam com a página
// porque é delas que a tela tira a ORDEM, o nome que o dono lê e a que área
// pertence cada fato. E o gerador é FAIL-CLOSED: sem o arquivo, o campo `area`
// dos registros não teria contra o que ser conferido e a aba desenharia todo
// mundo em "sem área reconhecida" — uma tela plausível e errada.
console.log("== as áreas do site viajam na página, e sem elas o gerador PARA ==");
var dirAreas = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") });
roda(dirAreas);
var htmlAreas = leia(dirAreas, "painel.html");
var doArquivo = JSON.parse(fs.readFileSync(path.join(RAIZ_PAINEL, "areas.json"), "utf8")).areas;
// Lida de dentro da página, executando o bloco embutido: prova que ela chega ao
// navegador como DADO, e não só que o texto aparece em algum lugar do arquivo.
var vmAreas = require("vm");
var NL = String.fromCharCode(10);
var caixaAreas = { window: {}, JSON: JSON };
try {
  var corpo = htmlAreas.split("var PAINEL = {")[1].split(NL + "};")[0];
  vmAreas.runInNewContext("var PAINEL = {" + corpo + NL + "};", caixaAreas, { timeout: 5000 });
} catch (e) { caixaAreas.PAINEL = null; }
caso("a página traz PAINEL.areas", !!(caixaAreas.PAINEL && caixaAreas.PAINEL.areas));
caso("...e é EXATAMENTE o que está em painel/areas.json (um lugar só)",
  !!caixaAreas.PAINEL && JSON.stringify(caixaAreas.PAINEL.areas) === JSON.stringify(doArquivo));
caso("...com a ordem do arquivo, que é a ordem da tela",
  !!caixaAreas.PAINEL && caixaAreas.PAINEL.areas.map(function (a) { return a.id; }).join(",") ===
    doArquivo.map(function (a) { return a.id; }).join(","));

var dirSemAreas = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") }, { semAreas: true });
var rSemAreas = roda(dirSemAreas);
caso("sem painel/areas.json o gerador RECUSA construir (exit 2 = ERROR)", rSemAreas.code === 2);
caso("...dizendo o caminho do arquivo que falta", rSemAreas.out.indexOf("areas.json") !== -1);
caso("...e NÃO escreve o painel", !existe(dirSemAreas, "painel.html"));

var dirAreasTortas = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") },
  { areas: "{ isto nao e json" });
caso("areas.json ilegível REPROVA (exit 2 = ERROR)", roda(dirAreasTortas).code === 2);

// Uma célula em duas áreas faria o mesmo trabalho aparecer em dois blocos, e a
// soma dos blocos deixaria de bater com a contagem do topo.
var dirAreasRepetidas = montarCenario({ "20260826-001-a.js": registroBom("20260826-001-a") }, {
  areas: JSON.stringify({ areas: [
    { id: "a", nome: "A", diz: "x", celulas: ["forum"] },
    { id: "b", nome: "B", diz: "y", celulas: ["forum"] }
  ] })
});
var rRepetidas = roda(dirAreasRepetidas);
caso("a mesma célula em duas áreas REPROVA (exit 1)", rRepetidas.code === 1);
caso("...e diz qual célula", rRepetidas.out.indexOf("forum") !== -1);
caso("...e NÃO escreve o painel", !existe(dirAreasRepetidas, "painel.html"));

// O campo `area` do registro é conferido contra este arquivo, no gerador, com a
// mesma logica.js da página: nome inventado não entra no livro.
var dirAreaBoa = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a", { area: "painel" })
});
caso("registro com 'area' de painel/areas.json passa", roda(dirAreaBoa).code === 0);
var dirAreaMa = montarCenario({
  "20260826-001-a.js": registroBom("20260826-001-a", { area: "celula-que-nao-existe" })
});
var rAreaMa = roda(dirAreaMa);
caso("registro com 'area' inventada REPROVA (exit 1)", rAreaMa.code === 1);
caso("...e diz qual nome não existe", rAreaMa.out.indexOf("celula-que-nao-existe") !== -1);

console.log("");
var templateDecisao = fs.readFileSync(path.join(RAIZ_PAINEL, "painel.template.html"), "utf8");
var fonteFicha = templateDecisao.slice(templateDecisao.indexOf("function fichaDaDecisao(r)"),
  templateDecisao.indexOf("  // ---------- a capa, calculada"));
var contextoFicha = {
  el: function (tag, classe, texto) {
    return { texto: texto || "", filhos: [], appendChild: function (filho) { this.filhos.push(filho); } };
  }
};
require("vm").runInNewContext(fonteFicha, contextoFicha);
var fichaCompleta = contextoFicha.fichaDaDecisao({
  porque_so_voce: "Só você pode autorizar essa despesa.",
  proximo_passo: "Aprovar ou recusar a contratação.",
  se_eu_nao_decidir: "O serviço atual continua ativo.",
  recomendacao: "Manter o serviço atual.", reversivel: false, impacto: "alto"
});
var linhasFicha = fichaCompleta.filhos.map(function (linha) {
  return linha.filhos.map(function (parte) { return parte.texto; }).join(": ");
});
caso("a ficha mostra a justificativa exclusiva do dono",
  linhasFicha.indexOf("Por que só você: Só você pode autorizar essa despesa.") !== -1);
caso("a ficha mostra o próximo passo concreto",
  linhasFicha.indexOf("Próximo passo: Aprovar ou recusar a contratação.") !== -1);
var fontePrioridade = templateDecisao.slice(templateDecisao.indexOf("function detalhesDePrioridade(i)"),
  templateDecisao.indexOf("  function itemDePrioridade(i, posicao)"));
require("vm").runInNewContext(fontePrioridade, contextoFicha);
var detalhesPedido = contextoFicha.detalhesDePrioridade({especie: "pedido", registro: {
  porque_so_voce: "Só você pode autorizar essa despesa.", proximo_passo: "Aprovar ou recusar."
}});
caso("a aba Prioridades mostra a justificativa exclusiva do dono",
  detalhesPedido.some(function (linha) { return linha[0] === "Por que só você" && linha[1] === "Só você pode autorizar essa despesa."; }));
caso("a aba Prioridades mostra o próximo passo concreto",
  detalhesPedido.some(function (linha) { return linha[0] === "Próximo passo" && linha[1] === "Aprovar ou recusar."; }));
var fichaAntiga = contextoFicha.fichaDaDecisao({});
caso("pedido antigo informa a ausência da justificativa sem desaparecer",
  fichaAntiga.filhos.some(function (linha) { return linha.filhos[1].texto === "O pedido antigo não explica por que esta decisão depende só de você."; }));
caso("pedido antigo informa a ausência de próximo passo sem desaparecer",
  fichaAntiga.filhos.some(function (linha) { return linha.filhos[1].texto === "O pedido antigo não registra um próximo passo claro."; }));

if (falhas.length) {
  console.error("❌ " + falhas.length + " caso(s) FALHARAM. O gerador NÃO está confiável.");
  process.exit(1);
}
console.log("✅ teste_gerador: todos os casos passaram.");
