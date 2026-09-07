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
//   abrir Prioridades       = +1 pedido (fila.json), e só; a vista é SÓ o menu
//   abrir uma área          = 0 pedido; SÓ o bloco daquela área na tela
//   tarefa na fila          tem o botão de copiar o prompt; a que espera o
//                           dono NÃO tem (07/09/2026, uma página por área)
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
// As áreas REAIS do site: a aba Prioridades desenha um cartão por área, e é
// contra esta lista que o menu é medido.
var AREAS = JSON.parse(fs.readFileSync(path.join(PAINEL, "areas.json"), "utf8")).areas;

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
  // `areas.json` entra na lista porque o gerador é fail-closed sem ele desde
  // 07/09/2026: são as áreas do site que a aba Prioridades desenha.
  ["logica.js", "gerar_manifesto.js", "painel.template.html", "areas.json"].forEach(function (f) {
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

/** A fila dos robôs como `fila_para_o_painel` (services/admin) a entrega: uma
 *  tarefa que um robô NOVO pode pegar (com `prompt`) e uma parada esperando o
 *  dono (sem), as duas na primeira área do site. A forma é a de
 *  `_tarefa_para_o_painel`, campo a campo, para medir a página real e não um
 *  dublê (armadilhas/131). */
var PROMPT_DO_STUB = "Toque a TAR-901 da fila de trabalho.\n\nO despacho inteiro está no arquivo dela.";
function filaDeMentira() {
  function tarefa(extra) {
    var base = { id: null, titulo: null, estado: null, espera: null, situacao: null,
      para_o_dono: false, importancia: null, selo: { texto: "ninguém classificou esta ainda", classe: "sem-nota" },
      area: AREAS[0].id, toca: ["admin"], onde: ["a área administrativa"], o_que_muda: null, motivo: null, prompt: null };
    Object.keys(extra).forEach(function (k) { base[k] = extra[k]; });
    return base;
  }
  return { erro: null, aviso: null, tarefas: [
    tarefa({ id: "TAR-901", titulo: "Uma tarefa esperando um robô", estado: "na fila",
      situacao: "Esperando um robô pegar", importancia: 70, selo: { texto: "custa caro hoje", classe: "alta" },
      o_que_muda: "o painel fica mais claro", prompt: PROMPT_DO_STUB }),
    tarefa({ id: "TAR-902", titulo: "Uma tarefa parada esperando o dono", estado: "bloqueada", espera: "mantenedor",
      situacao: "Esperando uma decisão sua", para_o_dono: true, motivo: "aguardando despacho do mantenedor" })
  ] };
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
    if (caminho === "/divida.json" || caminho === "/diag.json" || caminho === "/fila.json") {
      res.writeHead(200, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
      res.end(JSON.stringify(caminho === "/divida.json"
        ? { devedores: [] }
        : caminho === "/fila.json" ? filaDeMentira()
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

/** Os endereços que o painel busca DE PROPÓSITO fora da nossa origem.
 *
 *  Lista FECHADA, pelo mesmo motivo do orçamento de sub-pedidos ser nominal:
 *  um destino externo novo tem de passar por uma decisão consciente, não
 *  entrar de carona. Hoje são três, todos declarados no painel.template.html:
 *
 *    fonts.googleapis / gstatic   a tipografia da página
 *    api.github.com               as duas medições ao vivo (PRs abertos e
 *                                 execuções recentes)
 *    meshcraft.top                o `fetch` no-cors que prova que o site
 *                                 respondeu ao navegador agora
 */
var DESTINOS_EXTERNOS = [
  "fonts.googleapis.com",
  "fonts.gstatic.com",
  "api.github.com",
  "meshcraft.top",
];

function ehExterno(url) {
  for (var i = 0; i < DESTINOS_EXTERNOS.length; i++) {
    if (url.indexOf(DESTINOS_EXTERNOS[i]) !== -1) return true;
  }
  return false;
}

/** Só contam os pedidos à NOSSA origem: os destinos externos acima não
 *  atravessam a porta da área administrativa — misturá-los inflaria o
 *  orçamento com algo que ele não governa. */
function nossoPedido(pedidoUrl, base) {
  if (ehExterno(pedidoUrl)) return false;
  if (pedidoUrl.indexOf("favicon") !== -1) return false;
  return pedidoUrl.indexOf(base) === 0;
}

/** O MESMO CORTE, APLICADO AO ERRO DE CONSOLE — e é aqui que estava o defeito.
 *
 *  Achado pela auditoria interna de 29/08/2026. O orçamento de pedidos
 *  EXCLUÍA os destinos externos ("algo que ele não governa") e a contagem de
 *  erro de console os INCLUÍA. Resultado medido: num executor do GitHub, as
 *  duas chamadas do painel à `api.github.com` bateram no limite de consultas
 *  por IP e voltaram 403; o navegador registrou dois
 *  `Failed to load resource: 403`; e o guarda reprovou com
 *  "O painel NÃO cumpre o orçamento de amplificação".
 *
 *  O painel foi DESENHADO para sobreviver a isso — ele mesmo pinta
 *  "não consegui perguntar ao GitHub (sem internet ou limite de consultas).
 *  NÃO é um verde." Ou seja: o guarda chamava de defeito do painel um estado
 *  que o painel trata como esperado, e a mesma execução, repetida sem uma
 *  linha de diferença, passava. Guarda que pisca por causa da rede alheia
 *  ensina a ignorar vermelho — e nesta casa o merge depende de todo check
 *  estar verde (`ci/mergear.py`), então a piscada custava a etiqueta de pouso
 *  do PR e um comentário errado para o autor.
 *
 *  A distinção é FAIL contra ERROR (RETROSPECTIVA-FASE-D §1): "o painel está
 *  quebrado" e "não consegui medir o painel porque a rede lá fora falhou" são
 *  fatos diferentes. Os externos continuam SAINDO NO LOG — o que some é o
 *  poder de reprovar o painel por culpa de terceiro.
 *
 *  A METADE QUE ESCAPOU DAQUELA CURA, achada em 01/09/2026 pelo mesmo caminho:
 *  um PR sem defeito nenhum foi reprovado aqui, e o rerun ficou verde sem uma
 *  linha de diferença. O corte de 29/08 decide o dono pela ORIGEM da mensagem,
 *  e existe uma família de erro que o navegador reporta SEM origem declarada:
 *  o de CORS. Ele cai no `if (!origem) return true`, é adotado como nosso e
 *  reprova o painel — embora o único fato dentro dele seja um pedido barrado a
 *  um destino de terceiro. O 403 já era isento; o CORS não era.
 *
 *  POR QUE O CONSERTO ÓBVIO ESTÁ ERRADO, e esta é a parte que o próximo agente
 *  precisa ler antes de "simplificar" o que vem abaixo. A correção que salta
 *  aos olhos é "sem origem, veja se o TEXTO cita um destino externo". Ela tem
 *  uma mina: `DESTINOS_EXTERNOS` inclui `meshcraft.top`, que é o site DA CASA,
 *  e o painel tem links para ele na cara. Casamento por substring faria
 *  qualquer erro NOSSO cujo texto mencionasse esse endereço — um `TypeError`
 *  ao montar o link, por exemplo — perder o poder de reprovar. Seria trocar um
 *  guarda que pisca por um guarda que dorme, e o segundo é o pior dos dois: o
 *  primeiro faz barulho errado, o segundo faz silêncio errado.
 *
 *  O QUE FICA, em uma frase: sem origem declarada, o texto só isenta quando é
 *  um RELATO DO NAVEGADOR sobre um pedido barrado E o endereço desse pedido —
 *  lido de dentro da própria mensagem, em posição conhecida, não procurado
 *  nela — é um destino externo declarado. Não é "o texto menciona": é "o
 *  pedido que falhou era para". Menção nunca vira isenção, e a lista fechada
 *  continua governando também por este caminho.
 *
 *  As três fronteiras, todas deliberadas:
 *    · com origem declarada, é ELA quem decide, e o texto nem é olhado — tendo
 *      o fato melhor, não se recorre ao pior;
 *    · relato de pedido barrado cujo alvo é a NOSSA página continua nosso: a
 *      marca sozinha não isenta ninguém;
 *    · tudo que não couber nas duas regras acima cai no `return true`. Na
 *      dúvida, o dono é nosso — esse fail-closed é a regra certa e não se mexe.
 */

/** Os relatos em que o NAVEGADOR conta que um PEDIDO foi barrado — e dos quais
 *  dá para LER, dentro do próprio texto, o endereço que ele tentou alcançar.
 *
 *  Lista fechada como a dos destinos, e pelo mesmo motivo: cada entrada é uma
 *  frase que só o navegador escreve ao relatar rede, com o alvo em posição
 *  conhecida. Nada aqui procura endereço solto no meio do texto. */
var RELATOS_DE_PEDIDO_BARRADO = [
  // Access to fetch at 'https://api.github.com/…' from origin 'http://127.0.0.1:8123'
  //   has been blocked by CORS policy: No 'Access-Control-Allow-Origin' header …
  // (a forma é a mesma para fetch, XMLHttpRequest, script, font e stylesheet)
  { marca: "blocked by CORS policy", alvo: /Access to [^']*\bat '([^']+)'/ },
];

/** O pedido que este texto diz ter sido barrado ia para um destino externo
 *  declarado? Só isso isenta, e só quando o texto tem a forma de um relato. */
function pedidoBarradoParaDestinoExterno(texto) {
  for (var i = 0; i < RELATOS_DE_PEDIDO_BARRADO.length; i++) {
    var relato = RELATOS_DE_PEDIDO_BARRADO[i];
    if (texto.indexOf(relato.marca) === -1) continue;
    var achado = relato.alvo.exec(texto);
    if (!achado) continue;          // a marca sem alvo legível não isenta
    return ehExterno(achado[1]);    // e o alvo ainda passa pela lista fechada
  }
  return false;
}

function erroDaNossaPagina(mensagem) {
  var loc = mensagem.location && mensagem.location();
  var origem = (loc && loc.url) || "";
  if (origem) return !ehExterno(origem);
  var texto = (mensagem.text && mensagem.text()) || "";
  if (pedidoBarradoParaDestinoExterno(texto)) return false;
  return true;   // sem origem e sem relato de rede legível, o dono é nosso
}

async function medir(navegador, endereco, base, rotulo, esperados) {
  var pagina = await navegador.newPage();
  var pedidos = [];
  var errosConsole = [];
  var errosExternos = [];
  var errosPagina = [];
  pagina.on("request", function (r) {
    if (nossoPedido(r.url(), base)) pedidos.push(r.url());
  });
  pagina.on("console", function (m) {
    if (m.type() !== "error") return;
    var loc = m.location && m.location();
    var onde = (loc && loc.url) || "(sem origem)";
    if (erroDaNossaPagina(m)) errosConsole.push(m.text());
    else errosExternos.push(m.text() + "  [" + onde + "]");
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
  caso(rotulo + ": ZERO erro de console (da NOSSA página)", errosConsole.length === 0,
    errosConsole.slice(0, 3).join(" | "));
  // Os externos não reprovam, e por isso mesmo precisam APARECER: um destino
  // externo que passa a falhar sempre é notícia, e silêncio total aqui seria
  // trocar um alarme falso por uma cegueira.
  if (errosExternos.length) {
    console.log("  nota " + rotulo + ": " + errosExternos.length +
      " erro(s) de console vindos de destino EXTERNO (não reprovam; ver DESTINOS_EXTERNOS): " +
      errosExternos.slice(0, 3).join(" | "));
  }
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

/** Prioridades desde 07/09/2026: a aba é SÓ o menu, cada área tem a sua
 *  página, e a tarefa que um robô novo pode pegar traz o botão de copiar o
 *  prompt. Só pelo site: por duplo clique não há fila a buscar. */
async function medirPrioridades(estado, rotulo) {
  var pagina = estado.pagina;
  var antes = estado.pedidos.length;
  await pagina.evaluate(function () { location.hash = "#prioridades"; });
  await pagina.waitForTimeout(600);

  var menu = await pagina.evaluate(function () {
    return {
      cartoes: document.querySelectorAll("#vista-prioridades .card").length,
      temSem: !!document.querySelector('#vista-prioridades a.card[href="#area/sem"]'),
      blocos: document.querySelectorAll("#vista-prioridades .bloco").length,
      ativa: document.getElementById("vista-prioridades").className.indexOf("ativa") !== -1
    };
  });
  var esperados = AREAS.length + (menu.temSem ? 1 : 0);
  caso(rotulo + ": Prioridades é SÓ o menu, um cartão por área (" + esperados + ") e ZERO bloco",
    menu.ativa && menu.cartoes === esperados && menu.blocos === 0,
    "cartoes=" + menu.cartoes + " blocos=" + menu.blocos + " ativa=" + menu.ativa);
  var novos = estado.pedidos.slice(antes).map(function (u) { return u.split("/").pop(); });
  caso(rotulo + ": abrir Prioridades custa EXATAMENTE +1 pedido, o fila.json",
    JSON.stringify(novos) === JSON.stringify(["fila.json"]), "veio: " + (novos.join(", ") || "(nada)"));

  var depoisDaFila = estado.pedidos.length;
  await pagina.click("#vista-prioridades .card");
  await pagina.waitForTimeout(300);
  var area = await pagina.evaluate(function () {
    var cab = document.querySelector("#vista-area .bloco > .cab");
    return {
      hash: location.hash,
      ativa: document.getElementById("vista-area").className.indexOf("ativa") !== -1,
      abaAcesa: !!document.querySelector('.aba.ativa[data-vista="prioridades"]'),
      blocos: document.querySelectorAll("#vista-area .bloco").length,
      cab: cab ? cab.textContent : "",
      tarefas: document.querySelectorAll("#vista-area .item .meta").length,
      botoes: document.querySelectorAll("#vista-area .tocar").length,
      prompt: (document.querySelector("#vista-area .prompt-caixa") || {}).textContent || ""
    };
  });
  caso(rotulo + ": clicar no primeiro cartão abre #area/" + AREAS[0].id + ", com a aba Prioridades acesa",
    area.hash === "#area/" + AREAS[0].id && area.ativa && area.abaAcesa,
    "hash=" + area.hash + " ativa=" + area.ativa + " aba=" + area.abaAcesa);
  caso(rotulo + ": a página da área tem EXATAMENTE 1 bloco, com o nome da área no cabeçalho",
    area.blocos === 1 && area.cab.indexOf(AREAS[0].nome) === 0, "blocos=" + area.blocos + " cab=" + area.cab);
  caso(rotulo + ": abrir a área NÃO custou pedido novo (a fila já veio)",
    estado.pedidos.length === depoisDaFila, estado.pedidos.slice(depoisDaFila).join(" | "));
  caso(rotulo + ": só a tarefa na fila tem o botão de copiar, e o prompt é o da fila",
    area.tarefas === 2 && area.botoes === 1 && area.prompt === PROMPT_DO_STUB,
    "tarefas=" + area.tarefas + " botoes=" + area.botoes + " prompt=" + JSON.stringify(area.prompt.slice(0, 40)));

  await pagina.evaluate(function () { location.hash = "#area/nao-existe"; });
  await pagina.waitForTimeout(200);
  var perdida = await pagina.evaluate(function () {
    var volta = document.querySelector("#vista-area .voltar");
    return {
      ativa: document.getElementById("vista-area").className.indexOf("ativa") !== -1,
      texto: document.getElementById("area-bloco").textContent,
      blocos: document.querySelectorAll("#vista-area .bloco").length,
      volta: volta ? volta.getAttribute("href") : null
    };
  });
  caso(rotulo + ": área que não existe diz isso em português e oferece a volta, sem erro de página",
    perdida.ativa && perdida.blocos === 0 && perdida.texto.indexOf("Não existe área") === 0 &&
      perdida.volta === "#prioridades" && estado.errosPagina.length === 0,
    "texto=" + JSON.stringify(perdida.texto.slice(0, 50)) + " volta=" + perdida.volta +
      " erros=" + estado.errosPagina.slice(0, 2).join(" | "));
}

// ------------------------------------------------------ a prova do próprio corte

/** O corte "nosso × externo" tem de MORDER nos dois sentidos, e ser visto.
 *
 *  Sem isto, o conserto de 29/08/2026 seria uma regra escrita que ninguém
 *  encenou falhar (`armadilhas/132`): bastaria alguém trocar `!ehExterno` por
 *  `ehExterno` — ou esvaziar DESTINOS_EXTERNOS — para o guarda parar de olhar
 *  a própria página, e nada ficaria vermelho. Roda antes do navegador porque
 *  não precisa dele: é a classificação que está sob teste, não a rede.
 */
function provaDoCorteExterno() {
  function msg(origemUrl) {
    return { location: function () { return { url: origemUrl }; } };
  }
  // O erro de CORS chega SEM url de origem: tudo que se sabe do pedido barrado
  // está no texto. Esta segunda fábrica existe para encenar exatamente isso —
  // a de cima fica intocada, porque os casos dela são a metade do corte que já
  // estava provada desde 29/08/2026 e tem de continuar valendo igual.
  function msgSemOrigem(texto) {
    return {
      location: function () { return { url: "" }; },
      text: function () { return texto; },
    };
  }

  caso("corte externo: 403 da api.github.com NÃO reprova o painel",
    erroDaNossaPagina(msg("https://api.github.com/repos/x/y/pulls")) === false);
  caso("corte externo: falha das fontes do Google NÃO reprova o painel",
    erroDaNossaPagina(msg("https://fonts.googleapis.com/css2?family=X")) === false);
  caso("corte externo: erro na NOSSA página reprova",
    erroDaNossaPagina(msg("http://127.0.0.1:8123/painel.html")) === true);
  caso("corte externo: erro sem origem declarada reprova (o dono é nosso)",
    erroDaNossaPagina(msg("")) === true);
  caso("corte externo: destino externo NOVO reprova (a lista é fechada)",
    erroDaNossaPagina(msg("https://cdn.exemplo-que-ninguem-declarou.com/x.js")) === true);

  // ---- a metade de 01/09/2026: o erro SEM ORIGEM, que é onde o CORS cai ----

  // 1. O caso que reprovava um painel são. Só pode passar pelo caminho novo:
  //    a origem está vazia, e o único fato que isenta está dentro do texto.
  caso("corte CORS: pedido barrado à api.github.com NÃO reprova o painel",
    erroDaNossaPagina(msgSemOrigem(
      "Access to fetch at 'https://api.github.com/repos/abundanciabr/sitesdoreino/pulls' " +
      "from origin 'http://127.0.0.1:8123' has been blocked by CORS policy: " +
      "No 'Access-Control-Allow-Origin' header is present on the requested resource."
    )) === false);

  // 2. A MINA. Erro NOSSO que apenas MENCIONA o site da casa (o painel tem
  //    links para ele). Um casamento ingênuo por substring — a correção que
  //    salta aos olhos — adotaria isto como de terceiro e perderia o poder de
  //    reprovar. Este caso existe para que essa versão fique vermelha.
  caso("corte CORS: erro NOSSO que só MENCIONA meshcraft.top continua reprovando",
    erroDaNossaPagina(msgSemOrigem(
      "Uncaught TypeError: Cannot read properties of null (reading 'href') " +
      "ao montar o link para https://meshcraft.top/admin/painel/"
    )) === true);

  // 3. A mina pelo outro lado: a marca de pedido barrado ESTÁ lá, mas o alvo é
  //    a NOSSA página. Reconhecer o relato não basta — quem isenta é o alvo.
  caso("corte CORS: pedido barrado cuja vítima é a NOSSA página continua reprovando",
    erroDaNossaPagina(msgSemOrigem(
      "Access to fetch at 'http://127.0.0.1:8123/divida.json' from origin 'null' " +
      "has been blocked by CORS policy: Cross origin requests are only supported " +
      "for protocol schemes: http, https."
    )) === true);

  // 4. A lista fechada governa também por aqui: destino não declarado reprova,
  //    ainda que o navegador tenha dito, com todas as letras, que foi CORS.
  caso("corte CORS: pedido barrado a destino NÃO declarado reprova (a lista é fechada)",
    erroDaNossaPagina(msgSemOrigem(
      "Access to fetch at 'https://cdn.exemplo-que-ninguem-declarou.com/x.json' " +
      "from origin 'http://127.0.0.1:8123' has been blocked by CORS policy: " +
      "No 'Access-Control-Allow-Origin' header is present on the requested resource."
    )) === true);
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

  provaDoCorteExterno();

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
    await medirPrioridades(estadoHttp, "http · " + n);
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
  console.log("   Prioridades é só o menu, cada área tem a sua página, e a tarefa na fila tem o botão de copiar.");
  process.exit(0);
}

principal().catch(function (e) {
  erro("o rito não terminou: " + (e && e.stack ? e.stack : e));
});
