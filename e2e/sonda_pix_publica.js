#!/usr/bin/env node
// =============================================================================
// e2e/sonda_pix_publica.js: o Pix do site está vivo? Medido como um comprador.
//
// POR QUE EXISTE (TAR-803, frente N7 da obra Appmax)
// ---------------------------------------------------
// O cartão Appmax muda o checkout; o Pix precisa continuar no Mercado Pago
// (PLANO-MESTRE-APPMAX-NO-CARTAO.md §22.1, "Pix passou antes e depois"). Esta
// sonda responde isso de fora, num navegador de verdade, pelo mesmo caminho do
// comprador: /oferta, o botão de compra, o formulário, a página do Pix. Rode
// antes e depois de cada mudança do cartão (canário, rollback).
//
// O QUE ELA FAZ, E O QUE NUNCA FAZ
// --------------------------------
// Cria UM pedido Pix por execução, com um comprador sintético que se declara
// sonda (nome "Sonda Pix Publica", e-mail sonda-pix-<marca>@meshcraft.top, o
// padrão do canário da fase 3), e confere na página do Pix:
//   - o QR é uma imagem PNG que o navegador desenhou;
//   - o código copiável é um BR Code (começa em 000201, traz br.gov.bcb.pix e
//     fecha com o CRC16 certo) e tem o botão Copiar;
//   - a tela diz que o pagamento está aguardando.
// Nunca paga, nunca reenvia o formulário e nunca usa CPF: o pedido fica
// pendente e expira sozinho no Mercado Pago. Se a página do checkout disser
// que o Pix do site está na Appmax (ou não disser nada), a sonda NÃO cria
// pedido e reprova nomeando a causa: medir "Pix do Mercado Pago" onde ele
// não existe seria mentir, e o Pix Appmax exige CPF.
//
// O que sai no terminal e no JSON não tem e-mail, id bruto do pedido nem o
// conteúdo do código Pix: o pedido vira uma referência sha256 de 12 dígitos.
//
// Antes de tocar a rede, um AUTO-TESTE prova que cada leitor morde nos dois
// sentidos, contra páginas montadas no mesmo navegador.
//
// Uso:
//   npm install --no-save playwright@1.62.1 && npx playwright install chromium
//   node e2e/sonda_pix_publica.js                      (um pedido, JSON sanitizado no fim)
//   node e2e/sonda_pix_publica.js --so-auto-teste      (sem rede, sem pedido)
//   PAINEL_NAVEGADOR=chrome node e2e/sonda_pix_publica.js   (usa o Chrome do PC)
//
// Estados (RETROSPECTIVA-FASE-D §1): 0 PASS · 1 FAIL · 2 ERROR (não medido).
// =============================================================================
"use strict";
var crypto = require("crypto");

var BASE = "https://meshcraft.top";
var SO_AUTO_TESTE = process.argv.indexOf("--so-auto-teste") !== -1;

var MSG_PIX_NA_APPMAX =
  "o checkout declara o Pix deste site na Appmax (APPMAX_PIX_ENABLED_SITES): não há Pix do Mercado Pago para medir, e nenhum pedido foi criado";
var MSG_PROVEDOR_DESCONHECIDO =
  "o checkout não declara quem atende o Pix (appmax-pix-enabled ausente ou ilegível): nenhum pedido foi criado";
var MSG_QR_AUSENTE = "a página do Pix não desenhou o QR em PNG";
var MSG_CODIGO_AUSENTE = "a página do Pix não mostra o código copiável com o botão Copiar";
var MSG_CODIGO_INVALIDO = "o código copiável não é um BR Code Pix válido (000201, br.gov.bcb.pix e CRC16)";

var falhas = [];
function caso(nome, cond, detalhe) {
  if (cond) {
    console.log("  PASS " + nome);
  } else {
    console.error("  FAIL " + nome + (detalhe ? "  -> " + detalhe : ""));
    falhas.push(nome + (detalhe ? ": " + detalhe : ""));
  }
}
function erro(msg) {
  console.error("ERROR sonda_pix_publica: " + msg);
  console.error("   O Pix NÃO foi medido. Isto NÃO é um OK.");
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

// ------------------------------------------------------------------ leitores

/** CRC16/CCITT-FALSE, o do campo 63 do BR Code (Manual do BR Code, Bacen). */
function crc16(texto) {
  var crc = 0xffff;
  for (var i = 0; i < texto.length; i++) {
    crc ^= texto.charCodeAt(i) << 8;
    for (var b = 0; b < 8; b++) crc = crc & 0x8000 ? ((crc << 1) ^ 0x1021) & 0xffff : (crc << 1) & 0xffff;
  }
  return ("000" + crc.toString(16).toUpperCase()).slice(-4);
}

function brCodeValido(codigo) {
  if (!/^000201/.test(codigo) || !/br\.gov\.bcb\.pix/i.test(codigo)) return false;
  var fim = codigo.slice(-8);
  if (fim.slice(0, 4) !== "6304") return false;
  return crc16(codigo.slice(0, -4)) === fim.slice(4).toUpperCase();
}

/** Quem atende o Pix, segundo a própria página do checkout. Só "mercado_pago"
 *  autoriza criar pedido; qualquer outra leitura para antes do formulário. */
async function lerProvedorDoPix(pagina) {
  var bruto = await pagina.evaluate(function () {
    var el = document.getElementById("appmax-pix-provider") || document.getElementById("appmax-pix-enabled");
    return el ? el.textContent : null;
  });
  try {
    var valor = JSON.parse(bruto);
    if (valor === false) return "mercado_pago";
    if (valor === true) return "appmax";
  } catch (e) {}
  return "desconhecido";
}

/** O que a página do Pix mostra ao comprador, lido do DOM desenhado. */
async function lerPaginaDoPix(pagina) {
  var lido = await pagina.evaluate(function () {
    var img = document.querySelector("img.qr");
    var codigo = document.querySelector(".copia code");
    var botao = document.querySelector(".copia button");
    var visivel = function (el) { return !!el && el.offsetParent !== null; };
    var status = document.querySelector(".status");
    return {
      src: img && visivel(img) ? img.getAttribute("src") || "" : "",
      largura: img && img.complete ? img.naturalWidth : 0,
      codigo: codigo && visivel(codigo) ? (codigo.textContent || "").trim() : "",
      botao: visivel(botao) && /copiar/i.test(botao.textContent || ""),
      status: status ? (status.textContent || "").trim() : "",
    };
  });
  var png = /^data:image\/png;base64,/.test(lido.src)
    ? Buffer.from(lido.src.slice("data:image/png;base64,".length), "base64")
    : Buffer.alloc(0);
  var qrPresente = png.length > 8 && png.slice(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])) && lido.largura > 0;
  var falhasPix = [];
  if (!qrPresente) falhasPix.push(MSG_QR_AUSENTE);
  if (!lido.codigo || !lido.botao) falhasPix.push(MSG_CODIGO_AUSENTE);
  else if (!brCodeValido(lido.codigo)) falhasPix.push(MSG_CODIGO_INVALIDO);
  return {
    qr: { presente: qrPresente, bytes_png: png.length, largura_px: lido.largura },
    codigo: { presente: !!lido.codigo, tamanho: lido.codigo.length, br_code_valido: brCodeValido(lido.codigo), botao_copiar: lido.botao },
    status_na_tela: lido.status,
    falhas: falhasPix,
  };
}

function referencia(id) {
  return crypto.createHash("sha256").update(String(id)).digest("hex").slice(0, 12);
}

// --------------------------------------------------------------- auto-teste

var PNG_1X1 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
var BR_CODE_SEM_CRC =
  "00020126360014br.gov.bcb.pix0114+5500000000000520400005303986540599.905802BR5909SONDA PIX6009SAO PAULO62070503***6304";
var BR_CODE = BR_CODE_SEM_CRC + crc16(BR_CODE_SEM_CRC);
var SEM_PIX = BR_CODE_SEM_CRC.replace("br.gov.bcb.pix", "br.gov.bcb.xyz");
var SEM_INICIO = BR_CODE_SEM_CRC.replace(/^000201/, "000202");

function paginaDoPix(opcoes) {
  return (
    "<!doctype html><html><body><div class='card'>" +
    (opcoes.qr === false ? "" : "<img class='qr' alt='QR Code Pix' src='data:image/png;base64," + (opcoes.qr || PNG_1X1) + "'>") +
    (opcoes.codigo === false ? "" : "<p class='copia'><code>" + (opcoes.codigo || BR_CODE) + "</code>" + (opcoes.botao === false ? "" : "<button type='button'>Copiar</button>") + "</p>") +
    "<p class='status'>Aguardando confirmação do pagamento…</p></div></body></html>"
  );
}

async function autoTeste(navegador) {
  console.log("Auto-teste dos leitores (sem rede, sem pedido)");
  var pagina = await navegador.newPage();
  var cenarios = [
    ["checkout com Pix no Mercado Pago autoriza o pedido", "<script id='appmax-pix-enabled' type='application/json'>false</script>", "mercado_pago"],
    ["checkout com Pix na Appmax não autoriza", "<script id='appmax-pix-enabled' type='application/json'>true</script>", "appmax"],
    ["campos Appmax preparados com Pix primeiro no MP", "<script id='appmax-pix-enabled' type='application/json'>true</script><script id='appmax-pix-provider' type='application/json'>false</script>", "mercado_pago"],
    ["checkout sem a declaração não autoriza", "<p>sem declaração</p>", "desconhecido"],
  ];
  for (var i = 0; i < cenarios.length; i++) {
    await pagina.setContent(cenarios[i][1]);
    var provedor = await lerProvedorDoPix(pagina);
    caso(cenarios[i][0], provedor === cenarios[i][2], "leu " + provedor);
  }

  var pix = [
    ["QR e código válidos passam", {}, []],
    ["sem QR reprova", { qr: false }, [MSG_QR_AUSENTE]],
    ["QR que não é PNG reprova", { qr: Buffer.from("nao e png").toString("base64") }, [MSG_QR_AUSENTE]],
    ["sem código copiável reprova", { codigo: false }, [MSG_CODIGO_AUSENTE]],
    ["código sem o botão Copiar reprova", { botao: false }, [MSG_CODIGO_AUSENTE]],
    ["código com CRC errado reprova", { codigo: BR_CODE_SEM_CRC + "0000" }, [MSG_CODIGO_INVALIDO]],
    ["código que não começa em 000201 reprova, mesmo com CRC certo", { codigo: SEM_INICIO + crc16(SEM_INICIO) }, [MSG_CODIGO_INVALIDO]],
    ["código sem br.gov.bcb.pix reprova, mesmo com CRC certo", { codigo: SEM_PIX + crc16(SEM_PIX) }, [MSG_CODIGO_INVALIDO]],
  ];
  for (var j = 0; j < pix.length; j++) {
    await pagina.setContent(paginaDoPix(pix[j][1]));
    var lido = await lerPaginaDoPix(pagina);
    caso(pix[j][0], JSON.stringify(lido.falhas) === JSON.stringify(pix[j][2]), JSON.stringify(lido.falhas));
  }

  await pagina.setContent(paginaDoPix({}));
  var resultado = await lerPaginaDoPix(pagina);
  var texto = JSON.stringify({ pedido_ref: referencia("0b7a5c1e-0000-4000-8000-000000000000"), pix: resultado });
  caso(
    "o JSON não carrega o código Pix nem o id bruto do pedido",
    texto.indexOf(BR_CODE) === -1 && texto.indexOf("0b7a5c1e-0000") === -1 && texto.indexOf("SONDA PIX") === -1
  );
  await pagina.close();
}

// ------------------------------------------------------------- sonda viva

async function sonda(navegador, saida) {
  console.log("Sonda viva contra " + BASE);
  var contexto = await navegador.newContext();
  var pagina = await contexto.newPage();
  pagina.setDefaultTimeout(30000);

  await pagina.goto(BASE + "/oferta", { waitUntil: "domcontentloaded" });
  var checkout = await pagina.evaluate(function () {
    var a = document.querySelector("a[href*='/checkout/']");
    return a ? a.getAttribute("href") : "";
  });
  var oferta = (/\/checkout\/([a-z0-9-]+)\/?$/.exec(checkout) || [])[1] || "";
  caso("a página /oferta leva ao checkout", !!oferta, "nenhum link /checkout/<oferta>/ na página");
  if (!oferta) return;
  saida.oferta = oferta;

  await pagina.goto(BASE + "/checkout/" + oferta + "/", { waitUntil: "domcontentloaded" });
  saida.provedor_pix = await lerProvedorDoPix(pagina);
  if (saida.provedor_pix !== "mercado_pago") {
    caso("o Pix do site está no Mercado Pago", false, saida.provedor_pix === "appmax" ? MSG_PIX_NA_APPMAX : MSG_PROVEDOR_DESCONHECIDO);
    return;
  }

  await pagina.locator("#name").waitFor({ state: "visible" });
  var marca = new Date().toISOString().replace(/\D/g, "").slice(0, 14) + "-" + crypto.randomBytes(3).toString("hex");
  saida.marca_do_comprador = marca;
  await pagina.fill("#name", "Sonda Pix Publica");
  await pagina.fill("#email", "sonda-pix-" + marca + "@meshcraft.top");
  if (await pagina.locator("#phone").isVisible()) await pagina.fill("#phone", "11999999999");
  if (await pagina.locator("#cpf").isVisible()) await pagina.fill("#cpf", "40827365144");
  await pagina.click("button[type=button]:has-text('Pix')");

  var resposta = pagina.waitForResponse(function (r) {
    return r.request().method() === "POST" && /\/sessoes\/[^/]+\/pedido$/.test(r.url());
  }).then(async function (r) {
    return { ok: r.ok(), status: r.status(), pedido: r.ok() ? await r.json() : null };
  });
  saida.pedidos_criados = "incerto";
  await pagina.click("button.cta");
  var r = await resposta;
  saida.pedidos_criados = r.ok ? 1 : 0;
  saida.http_do_pedido = r.status;
  caso("o checkout aceitou o pedido Pix", r.ok, "HTTP " + r.status);
  if (!r.ok) return;

  var pedido = r.pedido || {};
  saida.pedido_ref = pedido.order_id ? referencia(pedido.order_id) : null;
  var naTelaDoPix = await pagina.waitForURL(/\/checkout\/pedido\/[^/]+\/pix\/$/).then(
    function () { return true; },
    function () { return false; }
  );
  caso("o comprador chegou à tela do Pix", naTelaDoPix, "o pedido foi aceito, mas a página não abriu a tela do Pix");
  if (!naTelaDoPix) return;
  await pagina
    .waitForFunction(function () {
      var img = document.querySelector("img.qr");
      return img && img.complete && img.naturalWidth > 0;
    })
    .catch(function () {});
  var lido = await lerPaginaDoPix(pagina);
  saida.pix = lido;
  caso("QR do Pix desenhado em PNG", lido.qr.presente, MSG_QR_AUSENTE);
  caso("código copiável BR Code com botão Copiar", lido.falhas.indexOf(MSG_CODIGO_AUSENTE) === -1 && lido.falhas.indexOf(MSG_CODIGO_INVALIDO) === -1, lido.falhas.join("; "));
  caso("a tela diz que o pagamento está aguardando", /aguardando/i.test(lido.status_na_tela), "status: " + lido.status_na_tela);
  await contexto.close();
}

// -------------------------------------------------------------------- main

(async function () {
  var saida = { sonda: "sonda_pix_publica", base: BASE, inicio_utc: new Date().toISOString(), pedidos_criados: 0 };
  var navegador;
  try {
    navegador = await playwright.chromium.launch(process.env.PAINEL_NAVEGADOR === "chrome" ? { channel: "chrome" } : {});
  } catch (e) {
    erro("o Chromium não abriu: " + e.message.split("\n")[0] + "\n   npx playwright install --with-deps chromium");
  }
  try {
    await autoTeste(navegador);
    if (falhas.length) {
      console.error("FAIL: o auto-teste reprovou; a sonda viva não roda com leitor quebrado.");
      process.exit(1);
    }
    if (!SO_AUTO_TESTE) await sonda(navegador, saida);
  } catch (e) {
    saida.erro = String(e.message || e).split("\n")[0]
      .replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, "<id>")
      .replace(/\S+@\S+/g, "<e-mail>");
  }
  await navegador.close();
  saida.fim_utc = new Date().toISOString();
  saida.veredito = saida.erro ? "ERROR" : falhas.length ? "FAIL" : "PASS";
  saida.falhas = falhas;
  if (!SO_AUTO_TESTE) console.log(JSON.stringify(saida, null, 2));
  if (saida.erro) {
    erro("a medição parou no meio: " + saida.erro + "\n   pedidos criados nesta execução: " + saida.pedidos_criados +
      (saida.pedido_ref ? " (referência " + saida.pedido_ref + "); confira esse pedido antes de repetir" : ""));
  }
  console.log(saida.veredito + (SO_AUTO_TESTE ? " (só auto-teste)" : ""));
  process.exit(falhas.length ? 1 : 0);
})();
