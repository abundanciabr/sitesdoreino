#!/usr/bin/env node
// =============================================================================
// e2e/ensaio_experimento.js — o ensaio L10 do sistema de experimentos, num
// navegador DE VERDADE (mesmo motivo de painel_no_navegador.js: o que decide o
// braço e dispara telemetria roda no JavaScript da página, e um test client
// que não executa JS não vê nenhum dos dois).
//
// O QUE ISTO PROVA
// -----------------
// Dois visitantes SEM COOKIE abrem `/oferta`. Cada um: lê o braço no HTML
// (`data-experimento-id` + `data-variante-id` no elemento do slot do
// experimento — os nomes que a F8b vai expor, DESENHO-COMUM.md), recarrega e
// confirma que o braço não mudou (sticky sem sessão no servidor), rola até a
// seção do slot, e clica no CTA SEM PAGAR — o clique é CAPTURADO antes de
// virar navegação de verdade (cancelado em fase de captura, no navegador;
// interceptar pela rede perde a corrida contra o clique com frequência
// medida ao vivo contra esta página, ver o comentário de
// `instalarCapturaDeClique`), então só se confirma que ele mirava `/checkout`.
// O visitante atribuído sai do próprio contexto do navegador
// (`context.cookies()`, que enxerga o `meshcraft_visitante` HttpOnly sem
// passar pelo `document.cookie` da página — services/funil/apps/core/
// visitante.py é explícito: o JS da página nunca lê esse cookie). As chamadas
// de rede a caminho da telemetria (xhr/fetch para a própria origem) são
// observadas e viajam no JSON de saída; a F3 (irmã em voo) ainda não expôs um
// caminho fixo, por isso aqui é OBSERVAÇÃO de rede, não uma chamada nomeada.
//
// SEM PÁGINA PRONTA AINDA, O ENSAIO FALHA DIZENDO O QUE FALTOU
// --------------------------------------------------------------
// Hoje (26/09/2026) nenhuma página em produção tem `data-experimento-id`: a
// F5 (catálogo)/F8a (sorteio)/F8b (expor no HTML) ainda não integraram. Rodar
// `--modo=ensaio` contra essa realidade tem de reprovar dizendo isso — nunca
// fingir que "sem experimento" é a mesma coisa que "a integração não chegou".
// Por isso o ensaio é um MODO EXPLÍCITO, separado do modo padrão:
//
//   --modo=rota     (padrão) PROVA 1: a rota funciona hoje, com ou sem
//                   experimento — visita, seção vista, CTA clicado e
//                   capturado antes de navegar. Roda contra produção AGORA e
//                   fecha verde.
//   --modo=ensaio   o ensaio L10 completo (braço sticky + exposição + clique
//                   + telemetria). Sem `data-experimento-id`/`data-variante-id`
//                   no HTML, reprova nomeando exatamente isso — nunca passa em
//                   falso. Use quando um experimento estiver ativo (bancada
//                   com F5+F8a+F8b, ou produção depois do primeiro
//                   experimento real).
//
// Antes dos dois, um AUTO-TESTE sem rede prova que o LEITOR do braço morde nos
// dois sentidos (achado/consistente vs. ausente vs. par quebrado) — a mesma
// forma de `provaDoCorteExterno()` em painel_no_navegador.js.
//
// Uso:
//   npm install --no-save playwright@1.62.1 && npx playwright install chromium
//   node e2e/ensaio_experimento.js                                    # prova 1, produção
//   BASE_URL=http://localhost:8000 node e2e/ensaio_experimento.js --modo=ensaio --saida=/tmp/ensaio.json
//   PAINEL_NAVEGADOR=chrome node e2e/ensaio_experimento.js            # usa o Chrome do PC
//
// Estados (RETROSPECTIVA-FASE-D §1): 0 PASS · 1 FAIL · 2 ERROR.
// =============================================================================
"use strict";
var fs = require("fs");
var os = require("os");
var path = require("path");

function argumento(nome, padrao) {
  var prefixo = "--" + nome + "=";
  for (var i = 0; i < process.argv.length; i++) {
    if (process.argv[i].indexOf(prefixo) === 0) return process.argv[i].slice(prefixo.length);
  }
  return padrao;
}

var MODO = argumento("modo", "rota");
var BASE = argumento("base", process.env.BASE_URL || "https://meshcraft.top").replace(/\/+$/, "");
var PAGINA_OFERTA = "/oferta";
var SAIDA_JSON = argumento("saida", process.env.SAIDA_JSON || "");

var falhas = [];
function caso(nome, cond, detalhe) {
  if (cond) {
    console.log("  PASS " + nome);
  } else {
    console.error("  FAIL " + nome + (detalhe ? "  -> " + detalhe : ""));
    falhas.push(nome);
  }
}
function erro(msg) {
  console.error("ERROR ensaio_experimento: " + msg);
  console.error("   O ensaio NÃO foi medido num navegador. Isto NÃO é um OK.");
  process.exit(2);
}

var playwright;
try {
  playwright = require("playwright");
} catch (e) {
  erro(
    "o pacote 'playwright' não está instalado.\n" +
      "   npm install --no-save playwright@1.62.1 && npx playwright install --with-deps chromium"
  );
}

// ---------------------------------------------------------- o leitor do braço

//: As mensagens exatas que este ensaio usa para dizer o que falta — citadas
//: aqui uma vez só (Lei 3) para o auto-teste e o ensaio de verdade concordarem
//: palavra por palavra.
var MSG_SEM_BRACO =
  "o slot não tem data-variante-id: experimento não está ativo ou a F8b não integrou";
var MSG_BRACO_INCONSISTENTE =
  "o slot tem data-experimento-id ou data-variante-id sozinho: o contrato exige os dois juntos (DESENHO-COMUM.md)";

/** O único fato que este ensaio lê do HTML: existe um elemento com o par de
 *  atributos do experimento? `found` distingue "nada disso existe na página"
 *  (o estado real de hoje) de "existe, mas quebrado" (`consistente=false`,
 *  só um dos dois presente) — os dois são falha, mas por motivos diferentes,
 *  e a mensagem de cada um tem de dizer qual. */
async function lerBraco(pagina) {
  return pagina.evaluate(function () {
    var comExperimento = document.querySelector("[data-experimento-id]");
    var comVariante = document.querySelector("[data-variante-id]");
    if (!comExperimento && !comVariante) {
      return { found: false, experimentoId: null, varianteId: null, consistente: true, seletor: null };
    }
    var elemento = comExperimento || comVariante;
    var experimentoId = elemento.getAttribute("data-experimento-id");
    var varianteId = elemento.getAttribute("data-variante-id");
    return {
      found: true,
      experimentoId: experimentoId,
      varianteId: varianteId,
      consistente: !!(experimentoId && varianteId),
      seletor: elemento.getAttribute("data-secao")
        ? "[data-secao=" + elemento.getAttribute("data-secao") + "]"
        : elemento.tagName.toLowerCase(),
    };
  });
}

/** Prova que `lerBraco` morde nos dois sentidos, SEM REDE — a mesma razão de
 *  `provaDoCorteExterno()` em painel_no_navegador.js: é a classificação que
 *  está sob teste, não a rede nem o experimento de verdade. Comentar a linha
 *  `consistente: !!(...)` (trocando por `true`) faz os casos 3 e 4 reprovarem
 *  — a mutação que prova que este guarda morde. */
async function provaDoLeitorDoBraco(navegador) {
  console.log("\n== auto-teste: o leitor do braço, sem rede ==");
  var contexto = await navegador.newContext();
  var pagina = await contexto.newPage();

  await pagina.setContent(
    '<section class="oferta-secao" data-secao="oferta" ' +
      'data-experimento-id="7c3a1e2e-0000-4000-8000-000000000001" data-variante-id="b">' +
      '<a class="cta" href="/checkout/x">Comprar</a></section>'
  );
  var comOsDois = await lerBraco(pagina);
  caso(
    "leitor: os dois atributos presentes -> achado e consistente",
    comOsDois.found &&
      comOsDois.consistente &&
      comOsDois.experimentoId === "7c3a1e2e-0000-4000-8000-000000000001" &&
      comOsDois.varianteId === "b"
  );

  await pagina.setContent(
    '<section class="oferta-secao" data-secao="oferta"><a class="cta" href="/checkout/x">Comprar</a></section>'
  );
  var semNenhum = await lerBraco(pagina);
  caso("leitor: nenhum atributo (o estado real de hoje) -> não achado", semNenhum.found === false);

  await pagina.setContent(
    '<section class="oferta-secao" data-secao="oferta" data-experimento-id="7c3a1e2e-0000-4000-8000-000000000001">' +
      '<a class="cta" href="/checkout/x">Comprar</a></section>'
  );
  var soExperimento = await lerBraco(pagina);
  caso(
    "leitor: só data-experimento-id -> achado e INCONSISTENTE",
    soExperimento.found && !soExperimento.consistente
  );

  await pagina.setContent(
    '<section class="oferta-secao" data-secao="oferta" data-variante-id="b">' +
      '<a class="cta" href="/checkout/x">Comprar</a></section>'
  );
  var soVariante = await lerBraco(pagina);
  caso("leitor: só data-variante-id -> achado e INCONSISTENTE", soVariante.found && !soVariante.consistente);

  await contexto.close();
}

// ------------------------------------------------------------------ o ensaio

/** As chamadas de rede desta origem que NÃO são documento nem estático — o
 *  candidato a telemetria enquanto a F3 não expõe um caminho fixo (o
 *  comentário de topo explica). */
function observarTelemetria(pagina) {
  var chamadas = [];
  pagina.on("requestfinished", function (req) {
    var tratar = (async function () {
      try {
        var reqUrl = req.url();
        if (reqUrl.indexOf(BASE) !== 0) return;
        var tipo = req.resourceType();
        if (tipo !== "xhr" && tipo !== "fetch" && tipo !== "other") return;
        var resp = await req.response();
        var corpo = null;
        if (resp) {
          try {
            corpo = await resp.json();
          } catch (e1) {
            try {
              corpo = (await resp.text()).slice(0, 500);
            } catch (e2) {
              corpo = null;
            }
          }
        }
        chamadas.push({ url: reqUrl, metodo: req.method(), status: resp ? resp.status() : null, corpo: corpo });
      } catch (e) {
        // rede instável durante a coleta não derruba o ensaio.
      }
    })();
    void tratar;
  });
  return chamadas;
}

/** Impede que o PRÓXIMO clique num `a.cta` chegue a navegar — confirma só que
 *  ele ACONTECEU (e para onde ia), sem pagar nada nem depender do serviço
 *  `checkout` estar de pé.
 *
 *  Isto NÃO é `page.route()`/`context.route()`, e a escolha é medida, não de
 *  gosto: as duas formas de interceptar pela REDE perdem a corrida contra a
 *  navegação real com frequência nesta página, ao vivo, em produção. O
 *  Chromium às vezes emite uma sondagem do link (ao passar o cursor ou
 *  pressionar o botão, antes do clique completar) que chega ao `route`
 *  classificada como "não é navegação"; o `continue()` daquela sondagem deixa
 *  a navegação REAL que vem em seguida passar sem bater no `route` de novo, e
 *  a página verdadeira de checkout chega a carregar — inclusive criando uma
 *  sessão de verdade em produção (medido ao vivo: `POST
 *  /checkout/api/checkout/sessoes`). Cancelar o próprio EVENTO DE CLIQUE não
 *  tem essa corrida: `preventDefault()` roda dentro do mesmo despacho de
 *  evento do clique, sempre ANTES de qualquer requisição de rede — não há
 *  janela de tempo em que o navegador já decidiu navegar mas o cancelamento
 *  ainda não chegou. `addInitScript` (e não `evaluate`) porque o clique deste
 *  ensaio acontece depois de um `reload`: um script instalado por `evaluate`
 *  morre com o documento antigo; o de `addInitScript` renasce em toda
 *  navegação da mesma página, sem precisar ser reinstalado. */
async function instalarCapturaDeClique(pagina) {
  await pagina.addInitScript(function () {
    window.__cliqueDoEnsaio = null;
    document.addEventListener(
      "click",
      function (evento) {
        var alvo = evento.target && evento.target.closest && evento.target.closest("a.cta");
        if (!alvo) return;
        evento.preventDefault();
        evento.stopPropagation();
        window.__cliqueDoEnsaio = alvo.href;
      },
      true
    );
  });
}

/** Clica no CTA e lê o que a captura de `instalarCapturaDeClique` registrou.
 *  `null` de volta significa duas coisas possíveis: o clique não achou nenhum
 *  `a.cta` no caminho do evento (guarda: `existeSecao`/`temCta` já cobrem
 *  isso antes), ou a captura não foi instalada — e aí o clique NAVEGOU de
 *  verdade, o que a prova seguinte (zero erro de página, braço intacto)
 *  também acabaria denunciando. */
async function clicarCtaSemNavegar(pagina, cta) {
  await cta.click();
  return pagina.evaluate(function () {
    return window.__cliqueDoEnsaio;
  });
}

/** Um visitante do ensaio L10, do zero: contexto novo (zero cookie), abre a
 *  oferta, prova o braço sticky, rola até o slot e clica no CTA. Devolve o
 *  registro que vai para o JSON de saída — inclusive quando falha, porque o
 *  que foi observado até a falha também é diagnóstico. */
async function visitanteDoEnsaio(navegador, rotulo) {
  var contexto = await navegador.newContext();
  var pagina = await contexto.newPage();
  await instalarCapturaDeClique(pagina);
  var telemetria = observarTelemetria(pagina);

  var resultado = {
    rotulo: rotulo,
    horario: new Date().toISOString(),
    visitorId: null,
    braco: null,
    checkoutInterceptado: null,
    telemetria: telemetria,
  };

  await pagina.goto(BASE + PAGINA_OFERTA, { waitUntil: "load", timeout: 30000 });

  var cookies = await contexto.cookies();
  var cookieVisitante = cookies.filter(function (c) {
    return c.name === "meshcraft_visitante";
  })[0];
  resultado.visitorId = cookieVisitante ? cookieVisitante.value : null;
  caso(rotulo + ": o servidor atribuiu um visitor_id (cookie meshcraft_visitante)", !!resultado.visitorId);

  var primeira = await lerBraco(pagina);
  if (!primeira.found) {
    caso(rotulo + ": o slot expõe o braço do experimento", false, MSG_SEM_BRACO);
    return resultado;
  }
  if (!primeira.consistente) {
    caso(rotulo + ": o par do braço está completo", false, MSG_BRACO_INCONSISTENTE + " (seletor: " + primeira.seletor + ")");
    return resultado;
  }
  caso(rotulo + ": o slot expõe data-experimento-id e data-variante-id juntos", true);
  resultado.braco = { experimentoId: primeira.experimentoId, varianteId: primeira.varianteId };

  await pagina.reload({ waitUntil: "load", timeout: 30000 });
  var segunda = await lerBraco(pagina);
  caso(
    rotulo + ": o braço não muda ao recarregar (sticky sem sessão no servidor)",
    segunda.found && segunda.experimentoId === primeira.experimentoId && segunda.varianteId === primeira.varianteId,
    "antes=" + JSON.stringify(primeira) + " depois=" + JSON.stringify(segunda)
  );

  var slot = pagina.locator("[data-experimento-id]").first();
  await slot.scrollIntoViewIfNeeded();
  caso(rotulo + ": a seção do slot ficou visível ao rolar", await slot.isVisible());

  var cta = pagina.locator("[data-experimento-id] a.cta").first();
  if ((await cta.count()) === 0) {
    cta = pagina.locator(
      "xpath=(//*[@data-experimento-id])[1]/ancestor-or-self::*[contains(concat(' ',normalize-space(@class),' '),' oferta-secao ')][1]//a[contains(concat(' ',normalize-space(@class),' '),' cta ')]"
    );
  }
  var temCta = (await cta.count()) > 0;
  caso(rotulo + ": existe um CTA associado à seção do slot", temCta);
  if (temCta) {
    var hrefCapturadoEnsaio = await clicarCtaSemNavegar(pagina, cta.first());
    resultado.checkoutInterceptado = hrefCapturadoEnsaio;
    caso(
      rotulo + ": o clique no CTA foi capturado a caminho de /checkout, sem pagar (sem navegar)",
      !!hrefCapturadoEnsaio && hrefCapturadoEnsaio.indexOf("/checkout") !== -1,
      "capturado=" + hrefCapturadoEnsaio
    );
  }

  return resultado;
}

async function ensaioDoBraco(navegador) {
  console.log("\n== ensaio L10: dois visitantes sem cookie, braço sticky, exposição e clique ==");
  var a = await visitanteDoEnsaio(navegador, "visitante A");
  var b = await visitanteDoEnsaio(navegador, "visitante B");
  return [a, b];
}

// -------------------------------------------------------------- prova 1: rota

/** PROVA 1 (deve fechar verde HOJE, contra produção, com ou sem experimento
 *  ativo): a rota em si funciona — a página abre, a seção da oferta aparece
 *  ao rolar, e o CTA mira `/checkout` de verdade quando clicado. Não olha
 *  `data-experimento-id`: é o piso que continua de pé mesmo sem nenhuma
 *  frente do experimento integrada. */
async function provaDaRota(navegador) {
  console.log("\n== prova 1: a rota funciona (com ou sem experimento ativo) ==");
  var contexto = await navegador.newContext();
  var pagina = await contexto.newPage();
  await instalarCapturaDeClique(pagina);
  var errosPagina = [];
  pagina.on("pageerror", function (e) {
    errosPagina.push(String(e && e.message ? e.message : e));
  });

  var resposta = await pagina.goto(BASE + PAGINA_OFERTA, { waitUntil: "load", timeout: 30000 });
  caso("rota: GET " + PAGINA_OFERTA + " respondeu 200", !!resposta && resposta.status() === 200, "status=" + (resposta && resposta.status()));

  var braco = await lerBraco(pagina);
  console.log(
    "  nota: data-experimento-id " +
      (braco.found ? "PRESENTE (" + braco.experimentoId + "/" + braco.varianteId + ")" : "ausente nesta página agora — nenhum experimento ativo, ou a F8b ainda não integrou")
  );

  var secao = pagina.locator("#a-oferta, [data-secao='oferta']").first();
  var existeSecao = (await secao.count()) > 0;
  caso("rota: a seção da oferta existe no HTML", existeSecao);
  if (existeSecao) {
    await secao.scrollIntoViewIfNeeded();
    caso("rota: a seção da oferta ficou visível ao rolar", await secao.isVisible());

    var cta = secao.locator("a.cta").first();
    var temCta = (await cta.count()) > 0;
    caso("rota: a seção da oferta tem um CTA", temCta);
    if (temCta) {
      var hrefCapturadoRota = await clicarCtaSemNavegar(pagina, cta);
      caso(
        "rota: o clique no CTA foi capturado a caminho de /checkout, sem pagar (sem navegar)",
        !!hrefCapturadoRota && hrefCapturadoRota.indexOf("/checkout") !== -1,
        "capturado=" + hrefCapturadoRota
      );
    }
  }
  caso("rota: zero erro de página", errosPagina.length === 0, errosPagina.slice(0, 3).join(" | "));

  await contexto.close();
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
        "   npx playwright install --with-deps chromium\n" +
        "   local: PAINEL_NAVEGADOR=chrome node e2e/ensaio_experimento.js"
    );
  }
  console.log("ENSAIO DO EXPERIMENTO — base " + BASE + PAGINA_OFERTA + " — modo " + MODO);

  await provaDoLeitorDoBraco(navegador);

  var resultados = null;
  if (MODO === "ensaio") {
    resultados = await ensaioDoBraco(navegador);
  } else if (MODO === "rota") {
    await provaDaRota(navegador);
  } else {
    await navegador.close();
    erro("--modo desconhecido: '" + MODO + "' (use --modo=rota ou --modo=ensaio)");
  }

  await navegador.close();

  if (resultados) {
    var caminho = SAIDA_JSON || path.join(os.tmpdir(), "ensaio-experimento-" + Date.now() + ".json");
    fs.writeFileSync(caminho, JSON.stringify(resultados, null, 2), "utf8");
    console.log("\nsaída JSON: " + caminho);
  }

  console.log("");
  if (falhas.length) {
    console.error("❌ " + falhas.length + " caso(s) FALHARAM (modo " + MODO + ").");
    if (MODO === "ensaio") {
      console.error(
        "   Se a falha citada foi '" + MSG_SEM_BRACO + "':\n" +
          "   isto é o ensaio dizendo o que falta, não um defeito do ensaio."
      );
    }
    process.exit(1);
  }
  console.log("✅ ensaio_experimento (modo " + MODO + "): nenhum caso falhou.");
  process.exit(0);
}

principal().catch(function (e) {
  erro("o rito não terminou: " + (e && e.stack ? e.stack : e));
});
