#!/usr/bin/env node
// =============================================================================
// e2e/painel_no_navegador.js — o painel medido num navegador DE VERDADE.
//
// POR QUE ISTO EXISTE, e por que nenhum outro teste substitui:
//
// O test client do Django não executa JavaScript. Ele conta `src="..."` no HTML
// e para aí. Desde 27/08/2026 o painel carrega o histórico por MÊS, injetando a
// tag de script em tempo de execução — coisa que nasce e morre dentro do
// navegador. Ou seja: o guarda que protege a propriedade "abrir o painel é UM
// pedido" **não consegue ver** a regressão em que a página passasse a carregar
// todos os meses ao abrir. Um guarda cego para aquilo que ele existe para
// proteger é pior que nenhum, porque dá a sensação de estar coberto.
//
// A casa já tem a armadilha escrita para a tentação de resolver isto com um DOM
// de mentira (`armadilhas/131` — dublê com forma diferente da real responde a
// outra pergunta). Por isso: navegador de verdade, ou nada.
//
// O QUE ELE AFIRMA (o Orçamento de Amplificação, medido em vez de prometido):
//
//   sub-pedidos ao abrir    = CONJUNTO NOMINAL, não contagem:
//                               file://  nenhum
//                               http     divida.json e diag.json, e só (as
//                                        medições ao vivo — custo FIXO, não
//                                        cresce com o livro)
//   erros de console        = 0
//   erros de página         = 0
//   a capa RENDERIZOU       (não é a tela vermelha)
//   abrir um mês            = +1 pedido, e só
//   os registros do mês     aparecem na tela
//
// Tudo isso com 10, 1.000 e 5.000 registros — é a forma da curva que importa,
// não o número num tamanho só. O conjunto é NOMINAL de propósito: contagem
// deixaria passar "sumiu um e apareceu outro", que é a mesma cegueira que a
// trava antiga do painel tinha.
//
// E nos DOIS modos de abrir, porque os dois são requisito do mantenedor:
// `file://` (duplo clique) e por um servidor HTTP.
//
// Uso:
//   node e2e/painel_no_navegador.js
//   PAINEL_NAVEGADOR=chrome node e2e/painel_no_navegador.js   (usa o Chrome do PC)
//
// Estados (RETROSPECTIVA-FASE-D §1): 0 PASS · 1 FAIL · 2 ERROR.
// =============================================================================
"use strict";
var fs = require("fs");
var os = require("os");
var path = require("path");
var http = require("http");
var cp = require("child_process");
var url = require("url");

var RAIZ = path.join(__dirname, "..");
var PAINEL = path.join(RAIZ, "painel");
var TAMANHOS = [10, 1000, 5000];

var falhas = [];
function caso(nome, cond, detalhe) {
  if (cond) {
    console.log("  PASS " + nome);
  } else {
    console.error("  FAIL " + nome + (detalhe ? "  → " + detalhe : ""));
    falhas.push(nome);
  }
}
function erro(msg) {
  console.error("❌ ERROR painel_no_navegador: " + msg);
  console.error("   O painel NÃO foi medido num navegador. Isto NÃO é um OK.");
  process.exit(2);
}

var playwright;
try {
  playwright = require("playwright");
} catch (e) {
  erro(
    "o pacote 'playwright' não está instalado.\n" +
      "   No CI: npm install playwright && npx playwright install --with-deps chromium\n" +
      "   Local: npm install --no-save playwright   (e use PAINEL_NAVEGADOR=chrome)"
  );
}

// ---------------------------------------------------------------- os cenários

function registroSintetico(base, dia) {
  return (
    "(function(){ (window.REGISTROS = window.REGISTROS || []).push(" +
    JSON.stringify({
      arquivo: base,
      tipo: "nota",
      quando: "2026-08-" + dia,
      titulo: "registro sintetico " + base,
      detalhe: "texto de teste",
      autoridade: "sessao",
      evidencia: null,
      verificado_em: null,
      precisa_do_dono: false,
      responde_a: null,
      gravidade: "info",
      frente: null,
      vence_em_dias: null,
    }) +
    ");})();"
  );
}

/** Um painel/ completo, gerado pelo gerador REAL, com N registros sintéticos. */
function cenario(n) {
  var dir = fs.mkdtempSync(path.join(os.tmpdir(), "painel-navegador-"));
  ["logica.js", "gerar_manifesto.js", "painel.template.html"].forEach(function (f) {
    fs.copyFileSync(path.join(PAINEL, f), path.join(dir, f));
  });
  fs.mkdirSync(path.join(dir, "registros"));
  for (var i = 1; i <= n; i++) {
    var dia = ("0" + (1 + (i % 28))).slice(-2);
    var base = "202608" + dia + "-" + ("00" + (i % 1000)).slice(-3) + "-r" + i;
    fs.writeFileSync(
      path.join(dir, "registros", base + ".js"),
      registroSintetico(base, dia),
      "utf8"
    );
  }
  var r = cp.spawnSync(process.execPath, [path.join(dir, "gerar_manifesto.js")], {
    encoding: "utf8",
    timeout: 600000,
  });
  if (r.status !== 0) {
    erro("o gerador não produziu o cenário de " + n + " registros:\n" + (r.stdout || "") + (r.stderr || ""));
  }
  return dir;
}

/** Servidor estático mínimo — o modo "pelo site", sem Django no caminho. */
function servidor(dir) {
  var s = http.createServer(function (req, res) {
    var alvo = path.join(dir, decodeURIComponent(url.parse(req.url).pathname));
    if (alvo.slice(-1) === path.sep || req.url === "/") alvo = path.join(dir, "painel.html");
    // A medição ao vivo da dívida do livro existe em produção
    // (`/admin/painel/divida.json`, servida por services/admin). O servidor
    // deste teste a serve também: sem isso o modo http mediria uma página
    // diferente da real, e um 404 inventado pelo teste apareceria como erro de
    // console — medindo o dublê em vez do original (armadilhas/131).
    var caminho = url.parse(req.url).pathname;
    if (caminho === "/divida.json" || caminho === "/diag.json") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
      res.end(JSON.stringify(caminho === "/divida.json"
        ? { devedores: [] }
        : { de_pe_ha_segundos: 42, perguntas_a_identidade: 3,
            desfechos: { respondeu: 3, estourou_o_tempo: 0, recusou: 0,
                         fora_do_contrato: 0, sem_configuracao: 0 },
            respostas_da_porta: { entrou: 3, mandou_para_o_login: 0,
                                  nao_existe_para_voce: 0, indisponivel_503: 0 },
            latencia_ms: { amostras: 3, p50: 4.2, p95: 7.1, maior: 7.1 },
            regua_ms: { saudavel_ate: 50, teto_da_porta: 2000 } }));
      return;
    }
    fs.readFile(alvo, function (e, dados) {
      if (e) {
        res.writeHead(404);
        res.end("nao encontrado");
        return;
      }
      var tipo = alvo.slice(-3) === ".js" ? "application/javascript" : "text/html";
      res.writeHead(200, { "Content-Type": tipo + "; charset=utf-8", "Cache-Control": "no-store" });
      res.end(dados);
    });
  });
  return new Promise(function (ok) {
    s.listen(0, "127.0.0.1", function () {
      ok({ servidor: s, porta: s.address().port });
    });
  });
}

// ------------------------------------------------------------------ a medição

/** Só contam os pedidos à NOSSA origem: as fontes do Google são externas e não
 *  atravessam a porta da área administrativa — misturá-las inflaria o
 *  orçamento com algo que ele não governa. */
function nossoPedido(pedidoUrl, base) {
  if (pedidoUrl.indexOf("fonts.googleapis.com") !== -1) return false;
  if (pedidoUrl.indexOf("fonts.gstatic.com") !== -1) return false;
  if (pedidoUrl.indexOf("favicon") !== -1) return false;
  return pedidoUrl.indexOf(base) === 0;
}

async function medir(navegador, endereco, base, rotulo, esperados) {
  var pagina = await navegador.newPage();
  var pedidos = [];
  var errosConsole = [];
  var errosPagina = [];
  pagina.on("request", function (r) {
    if (nossoPedido(r.url(), base)) pedidos.push(r.url());
  });
  pagina.on("console", function (m) {
    if (m.type() === "error") errosConsole.push(m.text());
  });
  pagina.on("pageerror", function (e) {
    errosPagina.push(String(e && e.message ? e.message : e));
  });

  await pagina.goto(endereco, { waitUntil: "load", timeout: 60000 });
  await pagina.waitForTimeout(300);

  // A página em si é o primeiro pedido. Tudo além dela é sub-recurso.
  var subPedidos = pedidos.filter(function (u) {
    return u !== endereco && u.replace(/\/$/, "") !== endereco.replace(/\/$/, "");
  });

  var telaErroVisivel = await pagina.evaluate(function () {
    var t = document.getElementById("tela-erro");
    return !!(t && t.style.display === "block");
  });
  var capaVisivel = await pagina.evaluate(function () {
    var a = document.getElementById("app");
    return !!(a && a.style.display === "block");
  });
  var itensNaCapa = await pagina.evaluate(function () {
    return document.querySelectorAll("#vista-capa .item").length;
  });

  console.log("  [" + rotulo + "]");
  caso(rotulo + ": a capa RENDERIZOU (não é a tela vermelha)", capaVisivel && !telaErroVisivel,
    "tela-erro=" + telaErroVisivel + " app=" + capaVisivel + " erros=" + JSON.stringify(errosPagina.slice(0, 2)));
  caso(rotulo + ": ZERO erro de página", errosPagina.length === 0, errosPagina.slice(0, 3).join(" | "));
  caso(rotulo + ": ZERO erro de console", errosConsole.length === 0, errosConsole.slice(0, 3).join(" | "));
  // O ORÇAMENTO É UM CONJUNTO, e não um número. Contagem deixaria passar
  // "sumiu um e apareceu outro" — a mesma cegueira que a trava antiga do painel
  // tinha. O que se afirma aqui é NOMINAL: exatamente estes sub-pedidos, e mais
  // nenhum. Um pedido novo (por mais inofensivo que pareça) tem de passar por
  // uma decisão consciente, não entrar de carona.
  var nomes = subPedidos.map(function (u) { return u.slice(base.length).replace(/^\//, ""); }).sort();
  var esperado = esperados.slice().sort();
  caso(rotulo + ": abrir o painel busca EXATAMENTE " +
      (esperado.length ? esperado.join(", ") : "nada"),
    JSON.stringify(nomes) === JSON.stringify(esperado),
    "veio: " + (nomes.join(", ") || "(nada)"));
  caso(rotulo + ": e NENHUM deles é registro ou mês do livro",
    nomes.filter(function (u) { return u.indexOf("registros/") === 0 || u.indexOf("livro-") === 0; }).length === 0,
    nomes.join(", "));
  caso(rotulo + ": a capa desenhou itens", itensNaCapa > 0, "itens=" + itensNaCapa);

  return { pagina: pagina, pedidos: pedidos, errosPagina: errosPagina };
}

/** A outra metade do orçamento: abrir um mês custa +1 pedido, e só. */
async function medirMemoria(estado, endereco, base, rotulo) {
  var pagina = estado.pagina;
  var antes = estado.pedidos.length;
  await pagina.evaluate(function () {
    location.hash = "#memoria";
  });
  await pagina.waitForTimeout(150);
  var botoes = await pagina.$$("#mem-registros .mes");
  if (!botoes.length) {
    caso(rotulo + ": a Memória oferece meses para carregar", false, "nenhum botão de mês");
    return;
  }
  caso(rotulo + ": a Memória oferece meses para carregar", true);
  await botoes[0].click();
  await pagina.waitForTimeout(1500);

  var depois = estado.pedidos.length;
  caso(rotulo + ": abrir um mês custa EXATAMENTE +1 pedido", depois - antes === 1,
    "foram " + (depois - antes) + ": " + estado.pedidos.slice(antes).join(" | "));

  var itens = await pagina.evaluate(function () {
    return document.querySelectorAll("#mem-registros .item").length;
  });
  caso(rotulo + ": o mês carregado desenhou registros na tela", itens > 0, "itens=" + itens);
  caso(rotulo + ": nenhum erro de página ao carregar o mês", estado.errosPagina.length === 0,
    estado.errosPagina.slice(0, 3).join(" | "));
}

// --------------------------------------------------------------------- o rito

async function principal() {
  var canal = process.env.PAINEL_NAVEGADOR || "";
  var opcoes = canal ? { channel: canal } : {};
  var navegador;
  try {
    navegador = await playwright.chromium.launch(opcoes);
  } catch (e) {
    erro(
      "não consegui abrir o navegador: " + e.message + "\n" +
        "   No CI: npx playwright install --with-deps chromium\n" +
        "   Local: PAINEL_NAVEGADOR=chrome node e2e/painel_no_navegador.js"
    );
  }
  console.log(
    "PAINEL NO NAVEGADOR — " + (canal ? "canal " + canal : "chromium do playwright")
  );

  for (var k = 0; k < TAMANHOS.length; k++) {
    var n = TAMANHOS[k];
    console.log("\n== " + n + " registros ==");
    var dir = cenario(n);

    // Modo 1: file:// — o duplo clique do mantenedor.
    var arquivo = url.pathToFileURL(path.join(dir, "painel.html")).href;
    var baseArquivo = url.pathToFileURL(dir).href;
    // Duplo clique: NADA além da própria página. Nem a medição da dívida —
    // sem servidor não há a quem perguntar, e a página sabe disso.
    var estadoArquivo = await medir(navegador, arquivo, baseArquivo, "file:// · " + n, []);
    await medirMemoria(estadoArquivo, arquivo, baseArquivo, "file:// · " + n);
    await estadoArquivo.pagina.close();

    // Modo 2: por um servidor — o caminho do site.
    var s = await servidor(dir);
    var endereco = "http://127.0.0.1:" + s.porta + "/painel.html";
    var baseHttp = "http://127.0.0.1:" + s.porta + "/";
    // Pelo site: a página mais a medição ao vivo da dívida do livro. Um pedido
    // FIXO — ele não cresce com o tamanho do livro, que é a propriedade que
    // este teste existe para proteger.
    // Pelo site: a página mais DUAS medições ao vivo — a dívida do livro e o
    // que o servidor diz sobre si mesmo. Pedidos FIXOS: não crescem com o
    // tamanho do livro, que é a propriedade que este teste existe para
    // proteger. O conjunto é nominal justamente para um pedido novo ter de
    // passar por uma decisão consciente, em vez de entrar de carona.
    var estadoHttp = await medir(navegador, endereco, baseHttp, "http · " + n,
      ["divida.json", "diag.json"]);
    await medirMemoria(estadoHttp, endereco, baseHttp, "http · " + n);
    await estadoHttp.pagina.close();
    s.servidor.close();
  }

  await navegador.close();

  console.log("");
  if (falhas.length) {
    console.error("❌ " + falhas.length + " caso(s) FALHARAM no navegador.");
    console.error("   O painel NÃO cumpre o orçamento de amplificação.");
    process.exit(1);
  }
  console.log("✅ painel_no_navegador: com 10, 1.000 e 5.000 registros, abrir o painel busca");
  console.log("   NADA por file:// e só as duas medições ao vivo pelo site — nos dois modos, sem");
  console.log("   erro de console e sem erro de página. O custo de abrir não cresce com o livro.");
  process.exit(0);
}

principal().catch(function (e) {
  erro("o rito não terminou: " + (e && e.stack ? e.stack : e));
});
