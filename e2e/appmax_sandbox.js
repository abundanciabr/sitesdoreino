#!/usr/bin/env node
// =============================================================================
// e2e/appmax_sandbox.js | a matriz oficial de cartões da Appmax sandbox, comprada
// PELA TELA de meshcraft.top num navegador de verdade (TAR-808).
//
// O QUE ISTO PROVA
// -----------------
// Para cada cartão do §16 de docs/decisoes/PLANO-MESTRE-APPMAX-NO-CARTAO.md,
// no computador e no celular, uma compra sintética NOVA atravessa a página de
// dados, a página do cartão, a tokenização da Appmax e a nossa API. Cada
// compra vira fatos medidos: o que a API respondeu a cada tentativa, o estado
// final do pedido, o que a tela mostrou e, pela rede, se o número do cartão ou
// o código de segurança saíram para qualquer lugar além da tokenização da
// Appmax. Depois, uma consulta de LEITURA na VPS conta, por pedido criado neste
// run, tentativas, operações, outbox, pedido e matrícula. O julgamento cruza
// as duas fontes com o resultado exigido de cada cartão.
//
// O QUE ISTO NUNCA FAZ
// ---------------------
// Não digita cartão se a página não carregou o script SANDBOX da Appmax. Não
// reenvia pedido antigo: cada compra nasce agora. Não liga nem desliga o
// cartão: se ele estiver desligado, sai em ERROR dizendo quem religa. Não
// publica o ID cru do pedido nem horário exato: o resumo leva SHA-256 curto e
// segundos desde o início do run.
//
// ETAPAS (o workflow .github/workflows/appmax-sandbox-tela.yml roda as três):
//   --etapa=auto-teste   sem rede: prova que auditoria, julgamento e leitor da
//                        VPS mordem nos dois sentidos.
//   --etapa=comprar      compra pela tela e grava --dados=<json> (IDs crus,
//                        só no runner) e --script=<sh> (consulta de leitura
//                        para a VPS).
//   --etapa=conferir     lê --dados e a saída da VPS em $SAIDA, julga cada
//                        cartão, publica o resumo sanitizado.
//
// SELEÇÃO (comprar e conferir): sem filtro, a matriz inteira (6 cartões x 2
// perfis = 12 compras). --cartao=<4 últimos dígitos> e --perfil=<desktop|celular>
// reduzem a matriz; valor que não existe reprova sem comprar nada.
//
// Uso local (compra de verdade no sandbox):
//   npm install --no-save playwright@1.62.1 && npx playwright install chromium
//   node e2e/appmax_sandbox.js --etapa=auto-teste
//   node e2e/appmax_sandbox.js --etapa=comprar --dados=/tmp/c.json --script=/tmp/c.sh
//   node e2e/appmax_sandbox.js --etapa=comprar --cartao=0010 --perfil=desktop ...
//
// Estados (RETROSPECTIVA-FASE-D §1): 0 PASS · 1 FAIL · 2 ERROR.
// =============================================================================
"use strict";
var crypto = require("crypto");
var fs = require("fs");

function argumento(nome, padrao) {
  var prefixo = "--" + nome + "=";
  for (var i = 0; i < process.argv.length; i++) {
    if (process.argv[i].indexOf(prefixo) === 0) return process.argv[i].slice(prefixo.length);
  }
  return padrao;
}

var ETAPA = argumento("etapa", "auto-teste");
var BASE = argumento("base", process.env.BASE_URL || "https://meshcraft.top").replace(/\/+$/, "");
var OFERTA = "curso-teste";
var SCRIPT_SANDBOX = "https://scripts.sandboxappmax.com.br/appmax.min.js";
// Os únicos destinos em que o número do cartão pode aparecer: a tokenização
// que o script sandbox da Appmax chama (medida em 27/09/2026) e o próprio
// domínio sandbox dela. Destino novo reprova nomeando o host: quem decide se
// ele é da Appmax é uma pessoa, não uma lista que cresce sozinha.
var HOSTS_DA_TOKENIZACAO = ["2ufaxwvzb7.execute-api.us-east-1.amazonaws.com"];
var SUFIXO_SANDBOX = ".sandboxappmax.com.br";

var CVV = "918";
var TITULAR = "TESTE SANDBOX";
var DOCUMENTO_DO_TITULAR = "12345678909";
var VALIDADE = { mes: "12", ano: "2030" };

var MATRIZ = [
  { cartao: "4000000000000010", caso: "aprovado", exigido: "aprovado, evento único, pedido pago e matrícula única" },
  { cartao: "4000000000000028", caso: "em_analise", exigido: "autorizado, continua em análise e não matricula" },
  { cartao: "4000000000000002", caso: "recusado", exigido: "recusado, permite nova tokenização" },
  { cartao: "4000000000000036", caso: "erro_transacional", exigido: "erro transacional, não queima o pedido" },
  { cartao: "4000000000000044", caso: "falha_do_pedido", exigido: "falha do pedido, não vira pagamento interno" },
  { cartao: "4000000000009999", caso: "indisponivel", exigido: "indisponibilidade, sem retry cego e sem afetar Pix" },
];
var PERFIS = ["desktop", "celular"];

/** A matriz que a rodada compra. Vazio significa "todos". Valor que não existe
 *  na matriz lança, e quem chama reprova antes de abrir o navegador. */
function selecionarMatriz(cartao, perfil) {
  var finais = MATRIZ.map(function (l) { return l.cartao.slice(-4); });
  var linhas = MATRIZ;
  var perfis = PERFIS;
  cartao = String(cartao || "").trim();
  perfil = String(perfil || "").trim();
  if (cartao) {
    linhas = MATRIZ.filter(function (l) { return l.cartao.slice(-4) === cartao; });
    if (!linhas.length) {
      throw new Error("o cartão '" + cartao + "' não existe na matriz. Informe os 4 últimos dígitos de um destes: " + finais.join(", ") + ". Nenhuma compra foi feita.");
    }
  }
  if (perfil) {
    perfis = PERFIS.filter(function (p) { return p === perfil; });
    if (!perfis.length) {
      throw new Error("o perfil '" + perfil + "' não existe na matriz. Informe um destes: " + PERFIS.join(", ") + ". Nenhuma compra foi feita.");
    }
  }
  return { linhas: linhas, perfis: perfis };
}

function selecaoDaLinhaDeComando() {
  try {
    return selecionarMatriz(argumento("cartao", ""), argumento("perfil", ""));
  } catch (e) {
    erro(e.message);
  }
}

var ESPERA_APROVACAO_MS = 150000;
var ESPERA_RESPOSTA_MS = 90000;
var JANELA_DE_OBSERVACAO_MS = 30000;
var RODAPE_DA_SSH =
  "\n" + "=".repeat(47) + "\n✅ Successfully executed commands to all hosts.\n" + "=".repeat(47);

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
  console.error("ERROR appmax_sandbox: " + msg);
  console.error("   A matriz NÃO foi medida. Isto NÃO é um OK.");
  process.exit(2);
}

function resumo(id) {
  return crypto.createHash("sha256").update(String(id)).digest("hex").slice(0, 16);
}

// ------------------------------------------------------------ a auditoria de rede

function contemCvv(valor) {
  if (valor === null || valor === undefined) return false;
  if (typeof valor === "number") return String(valor) === CVV;
  if (typeof valor === "string") return valor.trim() === CVV;
  if (Array.isArray(valor)) return valor.some(contemCvv);
  if (typeof valor === "object") {
    return Object.keys(valor).some(function (chave) {
      return /cvv|cvc|security_code|codigo_de_seguranca/i.test(chave) || contemCvv(valor[chave]);
    });
  }
  return false;
}

/** O que uma requisição carrega de dado do cartão. O CVV só conta como
 *  valor inteiro (JSON, parâmetro ou texto delimitado): três dígitos soltos
 *  aparecem dentro de qualquer UUID, e um detector que acusa todo UUID é um
 *  detector que a casa aprende a ignorar. */
function dadoDoCartao(url, corpo, pan) {
  var agrupado = pan.replace(/(\d{4})(?=\d)/g, "$1 ");
  var texto = String(url) + "\n" + String(corpo || "");
  var temPan = texto.indexOf(pan) !== -1 || texto.indexOf(agrupado) !== -1;
  var temCvv = false;
  try {
    temCvv = contemCvv(JSON.parse(corpo));
  } catch (e) {
    temCvv = new RegExp("(^|[^0-9A-Za-z])" + CVV + "([^0-9A-Za-z]|$)").test(String(corpo || ""));
  }
  var consulta = String(url).split("?")[1] || "";
  consulta.split("&").forEach(function (par) {
    var partes = par.split("=");
    if (/cvv|cvc|security/i.test(partes[0]) || decodeURIComponent(partes[1] || "") === CVV) temCvv = true;
  });
  return { pan: temPan, cvv: temCvv };
}

function destinoDaTokenizacao(host) {
  return HOSTS_DA_TOKENIZACAO.indexOf(host) !== -1 || host.slice(-SUFIXO_SANDBOX.length) === SUFIXO_SANDBOX;
}

/** Cada requisição vira uma linha sanitizada: host, caminho sem IDs, método e
 *  se levou dado do cartão. `vazou` é dado do cartão fora da tokenização. */
function registrarRequisicao(url, metodo, corpo, pan) {
  var endereco = new URL(url);
  var achado = dadoDoCartao(url, corpo, pan);
  return {
    host: endereco.host,
    caminho: endereco.pathname.replace(/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/g, ":id"),
    metodo: metodo,
    pan: achado.pan,
    cvv: achado.cvv,
    vazou: (achado.pan || achado.cvv) && !destinoDaTokenizacao(endereco.host),
  };
}

/** A trava antes de digitar qualquer cartão: a página carregou o script
 *  SANDBOX da Appmax e nenhum script de produção dela. */
function paginaEmSandbox(scripts) {
  return scripts.indexOf(SCRIPT_SANDBOX) !== -1 && !scripts.some(function (s) {
    return /\/\/scripts\.appmax\.com\.br\//.test(s);
  });
}

// --------------------------------------------------------------- o julgamento

function tentativaDoProvedor(t) {
  return t && t.http === 200 ? t.pagamento : "";
}

function aprovadas(outbox) {
  return (outbox && outbox["pagamento.aprovado"]) || 0;
}

/** Cruza os fatos da tela com a contagem da VPS e devolve a lista do que o
 *  cartão NÃO cumpriu. Lista vazia é o resultado exigido pelo §16. */
function julgar(compra, vps) {
  var faltas = [];
  var primeira = compra.tentativas[0] || {};
  var segunda = compra.tentativas[1] || null;
  var pag = vps && vps.pagamentos;
  if (!vps || !pag) return ["a VPS não devolveu contagem para este pedido"];
  var nenhumEfeito = function () {
    if (compra.status_final === "pago") faltas.push("o pedido virou pago");
    if (vps.pedido_status === "pago") faltas.push("o checkout gravou o pedido como pago");
    if (aprovadas(pag.outbox) !== 0) faltas.push("saiu pagamento.aprovado na outbox");
    if (vps.matriculas.length !== 0) faltas.push("nasceu matrícula");
  };
  if (compra.caso === "aprovado") {
    if (tentativaDoProvedor(primeira) !== "approved") faltas.push("a API não respondeu approved (http " + primeira.http + ")");
    if (compra.status_final !== "pago") faltas.push("o pedido não chegou a pago (" + compra.status_final + ")");
    if (compra.tela.status !== "Pagamento aprovado!") faltas.push("a tela não mostrou a aprovação");
    if (pag.tentativas.length !== 1) faltas.push("tentativas: " + pag.tentativas.length + ", esperada 1");
    if (aprovadas(pag.outbox) !== 1) faltas.push("pagamento.aprovado na outbox: " + aprovadas(pag.outbox) + ", esperado 1");
    if (vps.pedido_status !== "pago") faltas.push("checkout grava " + vps.pedido_status + ", esperado pago");
    if (vps.matriculas.length !== 1 || vps.matriculas[0] !== "ativa") {
      faltas.push("matrículas: " + JSON.stringify(vps.matriculas) + ", esperada uma ativa");
    }
  } else if (compra.caso === "em_analise") {
    if (tentativaDoProvedor(primeira) !== "pending") faltas.push("a API não respondeu pending (http " + primeira.http + ")");
    if (compra.status_final !== "aguardando_pagamento") faltas.push("o pedido saiu de aguardando_pagamento (" + compra.status_final + ")");
    nenhumEfeito();
  } else if (compra.caso === "recusado") {
    if (tentativaDoProvedor(primeira) !== "rejected") faltas.push("a API não respondeu rejected (http " + primeira.http + ")");
    if (compra.tela.erro.indexOf("Cartão recusado") === -1) faltas.push("a tela não disse que o cartão foi recusado");
    if (!segunda || tentativaDoProvedor(segunda) !== "rejected") {
      faltas.push("a nova tokenização não foi aceita (" + (segunda ? "http " + segunda.http : "sem segunda tentativa") + ")");
    }
    nenhumEfeito();
  } else if (compra.caso === "erro_transacional") {
    if (tentativaDoProvedor(primeira) === "approved") faltas.push("a API aprovou um erro transacional");
    if (!segunda || segunda.http !== 200) {
      faltas.push("o pedido ficou queimado: a nova tentativa não foi aceita (" + (segunda ? "http " + segunda.http : "sem segunda tentativa") + ")");
    }
    nenhumEfeito();
  } else if (compra.caso === "falha_do_pedido") {
    if (tentativaDoProvedor(primeira) === "approved") faltas.push("a API aprovou uma falha do pedido");
    if (!compra.tela.erro) faltas.push("a tela não explicou a falha");
    nenhumEfeito();
  } else if (compra.caso === "indisponivel") {
    if (tentativaDoProvedor(primeira) === "approved") faltas.push("a API aprovou durante indisponibilidade");
    if (pag.tentativas.length !== 1) faltas.push("tentativas: " + pag.tentativas.length + ", esperada 1 (retry cego)");
    pag.tentativas.forEach(function (t) {
      Object.keys(t.operacoes).forEach(function (tipo) {
        if (t.operacoes[tipo] > 1) faltas.push("operação " + tipo + " repetida " + t.operacoes[tipo] + " vezes");
      });
    });
    if (!compra.tela.erro) faltas.push("a tela não explicou a indisponibilidade");
    if (compra.pix_oferecido !== true) faltas.push("o Pix deixou de ser oferecido depois da indisponibilidade");
    nenhumEfeito();
  } else {
    faltas.push("caso desconhecido: " + compra.caso);
  }
  return faltas;
}

// ------------------------------------------------------ a consulta de leitura

var RESUMO = /^[0-9a-f]{16}$/;

/** O script que o workflow leva à VPS. Só lê: três consultas Django no
 *  contexto dos módulos da aplicação. Ele não carrega ID de pedido, só o resumo SHA-256 de cada pedido
 *  que ESTE run criou: o checkout acha, entre os pedidos das últimas seis
 *  horas, os que têm esses resumos, e só dentro da VPS o ID cru alimenta as
 *  consultas de pagamentos e alunos. A saída volta chaveada pelo resumo. */
function scriptDaVps(resumos) {
  if (!Array.isArray(resumos) || !resumos.length) throw new Error("nenhum pedido para contar");
  resumos.forEach(function (r) {
    if (!RESUMO.test(r)) throw new Error("resumo fora do formato de 16 hexadecimais: a consulta recusa montar");
  });
  var achar = [
    "import hashlib, json",
    "from datetime import timedelta",
    "from django.utils import timezone",
    "from apps.pedidos.models import Order",
    "procurados = set(" + JSON.stringify(resumos) + ")",
    "achados = {}",
    "for pk, status in Order.objects.filter(created_at__gte=timezone.now() - timedelta(hours=6)).values_list('pk', 'status'):",
    "    resumo = hashlib.sha256(str(pk).encode()).hexdigest()[:16]",
    "    if resumo in procurados:",
    "        achados[resumo] = {'id': str(pk), 'status': status}",
    "print('CONTAGEM:' + json.dumps(achados))",
  ].join("\n");
  var pagamentos = [
    "import json, re",
    "from collections import Counter",
    "from django.conf import settings",
    "from pagamentos.core.models import Intent, OutboxEvent, PaymentAttempt",
    "if settings.APPMAX_API_URL != 'https://api.sandboxappmax.com.br':",
    "    print('CONTAGEM:' + json.dumps({'sandbox': False}))",
    "    raise SystemExit(0)",
    "saida = {}",
    "for p in PEDIDOS:",
    "    tentativas = []",
    "    for t in PaymentAttempt.objects.filter(intent__order_id=p).order_by('created_at'):",
    "        motivo = t.reason if re.fullmatch(r'[a-z0-9_.:-]{0,120}', t.reason or '') else 'nao_sanitizado'",
    "        tentativas.append({'estado': t.state, 'motivo': motivo, 'operacoes': dict(Counter(o.operation_type for o in t.operacoes.all()))})",
    "    saida[p] = {'intents': sorted(i.status for i in Intent.objects.filter(order_id=p)), 'tentativas': tentativas, 'outbox': dict(Counter(OutboxEvent.objects.filter(payload__order_id=p).values_list('event', flat=True)))}",
    "print('CONTAGEM:' + json.dumps({'sandbox': True, 'pedidos': saida}))",
  ].join("\n");
  var alunos = [
    "import json",
    "from apps.matriculas.models import Matricula",
    "print('CONTAGEM:' + json.dumps({p: sorted(Matricula.objects.filter(order_id=p).values_list('status', flat=True)) for p in PEDIDOS}))",
  ].join("\n");
  var host = [
    "import json, re, subprocess",
    "def falhar(codigo):",
    "    print(json.dumps({'resultado': 'ERROR', 'erro': codigo}))",
    "    raise SystemExit(2)",
    "def django(servico, codigo):",
    "    try:",
    "        ident = subprocess.run(['docker', 'ps', '--quiet', '--no-trunc', '--filter', 'label=com.docker.compose.project=plataforma', '--filter', 'label=com.docker.compose.service=aplicacao', '--filter', 'status=running'], capture_output=True, text=True, timeout=30, check=False).stdout.strip()",
    "        if not re.fullmatch(r'[0-9a-f]{12,64}', ident):",
    "            falhar('conteiner_aplicacao')",
    "        r = subprocess.run(['docker', 'exec', '-i', ident, 'python', '-m', 'config.executar', servico, '-'], input=codigo, capture_output=True, text=True, timeout=90, check=False)",
    "    except (OSError, subprocess.TimeoutExpired):",
    "        falhar('instrumento_' + servico)",
    "    linhas = [l[len('CONTAGEM:'):] for l in r.stdout.splitlines() if l.startswith('CONTAGEM:')]",
    "    if r.returncode or len(linhas) != 1:",
    "        falhar('consulta_' + servico)",
    "    return json.loads(linhas[0])",
    "achados = django('checkout', " + JSON.stringify(achar) + ")",
    "pedidos = [a['id'] for a in achados.values()]",
    "if not pedidos or not all(re.fullmatch(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', p) for p in pedidos):",
    "    falhar('pedidos_nao_encontrados')",
    "pagamentos = django('pagamentos', 'PEDIDOS = ' + repr(pedidos) + '\\n' + " + JSON.stringify(pagamentos) + ")",
    "if not pagamentos.get('sandbox'):",
    "    falhar('appmax_fora_do_sandbox')",
    "alunos = django('alunos', 'PEDIDOS = ' + repr(pedidos) + '\\n' + " + JSON.stringify(alunos) + ")",
    "print(json.dumps({'resultado': 'PASS', 'pedidos': {r: {'pagamentos': pagamentos['pedidos'][a['id']], 'pedido_status': a['status'], 'matriculas': alunos[a['id']]} for r, a in achados.items()}}, sort_keys=True))",
  ].join("\n");
  // O ssh-action fecha a saída multilinha com `echo EOF` sob `bash -e -o
  // pipefail`: saída diferente de zero aqui apaga a evidência. O veredito vem
  // do JSON, em `lerSaidaDaVps` (armadilha do PR #2249/TAR-868).
  return "set -eu\npython3 - <<'PY_CONTAGEM_APPMAX' || true\n" + host + "\nPY_CONTAGEM_APPMAX\n";
}

/** A saída da ação SSH chega com o rodapé dela colado. Qualquer coisa que não
 *  seja o JSON de PASS da consulta é ERROR, nunca "sem contagem = zero". */
function lerSaidaDaVps(bruta) {
  var texto = String(bruta || "").trim();
  if (texto.slice(-RODAPE_DA_SSH.length) === RODAPE_DA_SSH) texto = texto.slice(0, -RODAPE_DA_SSH.length).trim();
  var dados;
  try {
    dados = JSON.parse(texto);
  } catch (e) {
    throw new Error("a saída da VPS não é JSON");
  }
  if (!dados || dados.resultado !== "PASS" || typeof dados.pedidos !== "object") {
    throw new Error("a VPS não devolveu PASS: " + JSON.stringify(dados && dados.erro ? { erro: dados.erro } : {}));
  }
  return dados.pedidos;
}

// --------------------------------------------------------------- o auto-teste

function fatoBase(caso) {
  return {
    caso: caso,
    tentativas: [],
    status_final: "aguardando_pagamento",
    tela: { status: "", erro: "" },
    pix_oferecido: null,
  };
}

function vpsBase() {
  return { pagamentos: { intents: ["created"], tentativas: [], outbox: {} }, pedido_status: "aguardando_pagamento", matriculas: [] };
}

function exemplosQueCumprem() {
  var aprovado = fatoBase("aprovado");
  aprovado.tentativas = [{ http: 200, pagamento: "approved" }];
  aprovado.status_final = "pago";
  aprovado.tela.status = "Pagamento aprovado!";
  var vAprovado = vpsBase();
  vAprovado.pagamentos.tentativas = [{ estado: "approved", motivo: "", operacoes: { customer: 1, order: 1, payment: 1 } }];
  vAprovado.pagamentos.outbox = { "pagamento.aprovado": 1 };
  vAprovado.pedido_status = "pago";
  vAprovado.matriculas = ["ativa"];

  var analise = fatoBase("em_analise");
  analise.tentativas = [{ http: 200, pagamento: "pending" }];
  var vAnalise = vpsBase();
  vAnalise.pagamentos.tentativas = [{ estado: "pending", motivo: "", operacoes: { payment: 1 } }];

  var recusado = fatoBase("recusado");
  recusado.tentativas = [{ http: 200, pagamento: "rejected" }, { http: 200, pagamento: "rejected" }];
  recusado.status_final = "recusado";
  recusado.tela.erro = "Cartão recusado. Confira os dados ou tente outro cartão.";
  var vRecusado = vpsBase();
  vRecusado.pagamentos.outbox = { "pagamento.recusado": 1 };

  var transacional = fatoBase("erro_transacional");
  transacional.tentativas = [{ http: 200, pagamento: "rejected" }, { http: 200, pagamento: "rejected" }];

  var falhaPedido = fatoBase("falha_do_pedido");
  falhaPedido.tentativas = [{ http: 502, pagamento: "" }];
  falhaPedido.tela.erro = "Não foi possível concluir a tentativa. Tente novamente.";

  var indisponivel = fatoBase("indisponivel");
  indisponivel.tentativas = [{ http: 502, pagamento: "" }];
  indisponivel.tela.erro = "Não foi possível concluir a tentativa. Tente novamente.";
  indisponivel.pix_oferecido = true;
  var vIndisponivel = vpsBase();
  vIndisponivel.pagamentos.tentativas = [{ estado: "failed", motivo: "", operacoes: { customer: 1, order: 1 } }];

  return [
    [aprovado, vAprovado],
    [analise, vAnalise],
    [recusado, vRecusado],
    [transacional, vpsBase()],
    [falhaPedido, vpsBase()],
    [indisponivel, vIndisponivel],
  ];
}

function copia(x) {
  return JSON.parse(JSON.stringify(x));
}

function autoTeste() {
  console.log("AUTO-TESTE (sem rede)");
  var pan = MATRIZ[0].cartao;

  caso("auditoria: PAN no corpo para a nossa API é vazamento",
    registrarRequisicao(BASE + "/checkout/api/checkout/pedidos/x/cartao", "POST", JSON.stringify({ token: pan }), pan).vazou === true);
  caso("auditoria: PAN agrupado em quatro também é vazamento",
    registrarRequisicao(BASE + "/x", "POST", "numero=4000 0000 0000 0010", pan).vazou === true);
  caso("auditoria: PAN na tokenização da Appmax sandbox é o destino certo",
    registrarRequisicao("https://" + HOSTS_DA_TOKENIZACAO[0] + "/development/v1/payments/tokenize", "POST", JSON.stringify({ number: pan }), pan).vazou === false);
  caso("auditoria: PAN para host desconhecido é vazamento",
    registrarRequisicao("https://coletor.exemplo.test/v1/payments/tokenize", "POST", JSON.stringify({ number: pan }), pan).vazou === true);
  caso("auditoria: CVV como valor JSON para a nossa API é vazamento",
    registrarRequisicao(BASE + "/x", "POST", JSON.stringify({ a: { b: CVV } }), pan).vazou === true);
  caso("auditoria: campo cvv para a nossa API é vazamento mesmo vazio",
    registrarRequisicao(BASE + "/x", "POST", JSON.stringify({ cvv: "" }), pan).vazou === true);
  caso("auditoria: CVV em parâmetro de URL é vazamento",
    registrarRequisicao(BASE + "/x?c=" + CVV, "GET", "", pan).vazou === true);
  caso("auditoria: os três dígitos dentro de um UUID não são CVV",
    registrarRequisicao(BASE + "/pedidos/31d66b39-f298-4060-97f6-d44a6" + CVV + "41a0", "GET", "", pan).vazou === false);
  caso("auditoria: o caminho publicado não leva o UUID cru",
    registrarRequisicao(BASE + "/pedidos/31d66b39-f298-4060-97f6-d44a64ee41a0/cartao", "GET", "", pan).caminho === "/pedidos/:id/cartao");

  caso("trava: página com o script sandbox libera a digitação", paginaEmSandbox([BASE + "/checkout/static/checkout/api.js", SCRIPT_SANDBOX]));
  caso("trava: página com o script de produção da Appmax não libera", !paginaEmSandbox([SCRIPT_SANDBOX, "https://scripts.appmax.com.br/appmax.min.js"]));
  caso("trava: página sem script da Appmax não libera", !paginaEmSandbox([BASE + "/checkout/static/checkout/cartao.js"]));

  exemplosQueCumprem().forEach(function (par) {
    var faltas = julgar(par[0], par[1]);
    caso("julgamento: " + par[0].caso + " no resultado exigido passa", faltas.length === 0, faltas.join("; "));
  });

  var sabotagens = [
    ["aprovado com duas matrículas", 0, function (f, v) { v.matriculas = ["ativa", "ativa"]; }],
    ["aprovado com dois eventos aprovados", 0, function (f, v) { v.pagamentos.outbox["pagamento.aprovado"] = 2; }],
    ["aprovado com duas tentativas", 0, function (f, v) { v.pagamentos.tentativas.push(v.pagamentos.tentativas[0]); }],
    ["aprovado sem pedido pago", 0, function (f, v) { v.pedido_status = "aguardando_pagamento"; }],
    ["aprovado sem a tela de aprovação", 0, function (f) { f.tela.status = "Aguardando pagamento."; }],
    ["em análise que matriculou", 1, function (f, v) { v.matriculas = ["ativa"]; }],
    ["em análise que virou pago", 1, function (f) { f.status_final = "pago"; }],
    ["recusado com HTTP 500", 2, function (f) { f.tentativas[0] = { http: 500, pagamento: "" }; }],
    ["recusado sem nova tokenização", 2, function (f) { f.tentativas.pop(); }],
    ["recusado sem explicar na tela", 2, function (f) { f.tela.erro = ""; }],
    ["erro transacional que queimou o pedido", 3, function (f) { f.tentativas[1] = { http: 409, pagamento: "" }; }],
    ["falha do pedido que emitiu aprovado", 4, function (f, v) { v.pagamentos.outbox["pagamento.aprovado"] = 1; }],
    ["indisponível com retry cego", 5, function (f, v) { v.pagamentos.tentativas.push(v.pagamentos.tentativas[0]); }],
    ["indisponível com operação repetida", 5, function (f, v) { v.pagamentos.tentativas[0].operacoes.order = 2; }],
    ["indisponível que tirou o Pix", 5, function (f) { f.pix_oferecido = false; }],
  ];
  sabotagens.forEach(function (s) {
    var par = copia(exemplosQueCumprem()[s[1]]);
    s[2](par[0], par[1]);
    caso("julgamento: " + s[0] + " reprova", julgar(par[0], par[1]).length > 0);
  });
  caso("julgamento: pedido sem contagem da VPS reprova", julgar(exemplosQueCumprem()[0][0], null).length > 0);

  var pedido = "31d66b39-f298-4060-97f6-d44a64ee41a0";
  var script = scriptDaVps([resumo(pedido)]);
  caso("consulta: recusa texto que não é resumo", (function () {
    try { scriptDaVps(["1; rm -rf /"]); return false; } catch (e) { return true; }
  })());
  caso("consulta: recusa o ID cru do pedido", (function () {
    try { scriptDaVps([pedido]); return false; } catch (e) { return true; }
  })());
  caso("consulta: recusa lista vazia", (function () {
    try { scriptDaVps([]); return false; } catch (e) { return true; }
  })());
  caso("consulta: exige Appmax sandbox antes de contar", script.indexOf("appmax_fora_do_sandbox") !== -1 &&
    script.indexOf("https://api.sandboxappmax.com.br") !== -1);
  caso("consulta: só lê (nenhuma escrita de ORM)", !/\.(save|delete|update|create|bulk_create)\(/.test(script));
  caso("consulta: usa a aplicação única com contexto dos três módulos",
    script.indexOf("service=aplicacao") !== -1 &&
    script.indexOf("config.executar") !== -1 &&
    script.indexOf("django('checkout'") !== -1 &&
    script.indexOf("django('pagamentos'") !== -1 &&
    script.indexOf("django('alunos'") !== -1);
  caso("consulta: o script leva só o resumo do pedido", script.indexOf(resumo(pedido)) !== -1 && script.indexOf(pedido) === -1);
  // PR #2249 (TAR-868), replicado aqui: sob `bash -e -o pipefail`, o ssh-action
  // fecha a captura multilinha do stdout com um `echo EOF` que só roda se o
  // comando anterior saiu 0. Sem isto, ERROR no remoto apaga a evidência bem
  // no caso em que mais precisamos dela. O veredito vem do JSON, em `lerSaidaDaVps`.
  caso("consulta: o script remoto sai sempre 0 (evidência não some em ERROR)",
    script.indexOf("<<'PY_CONTAGEM_APPMAX' || true\n") !== -1);

  var todas = selecionarMatriz("", "");
  caso("seleção: sem filtro compra 12 (6 cartões x 2 perfis)", todas.linhas.length * todas.perfis.length === 12);
  var uma = selecionarMatriz("0010", "celular");
  caso("seleção: um cartão e um perfil compram 1",
    uma.linhas.length * uma.perfis.length === 1 && uma.linhas[0].cartao === "4000000000000010" && uma.perfis[0] === "celular");
  caso("seleção: só o cartão compra os dois perfis", (function () {
    var s = selecionarMatriz("0028", "");
    return s.linhas.length * s.perfis.length === 2;
  })());
  caso("seleção: só o perfil compra os seis cartões", (function () {
    var s = selecionarMatriz("", "desktop");
    return s.linhas.length * s.perfis.length === 6;
  })());
  caso("seleção: cartão inexistente reprova e lista os valores válidos", (function () {
    try { selecionarMatriz("1234", ""); return false; } catch (e) { return e.message.indexOf("0010") !== -1 && e.message.indexOf("Nenhuma compra") !== -1; }
  })());
  caso("seleção: o número inteiro do cartão não vale, só os 4 últimos dígitos", (function () {
    try { selecionarMatriz("4000000000000010", ""); return false; } catch (e) { return true; }
  })());
  caso("seleção: perfil inexistente reprova e lista os valores válidos", (function () {
    try { selecionarMatriz("", "tablet"); return false; } catch (e) { return e.message.indexOf("celular") !== -1 && e.message.indexOf("Nenhuma compra") !== -1; }
  })());

  var saida = JSON.stringify({ resultado: "PASS", pedidos: { abc: 1 } });
  caso("leitor da VPS: tira o rodapé da ação SSH", lerSaidaDaVps(saida + RODAPE_DA_SSH).abc === 1);
  caso("leitor da VPS: ERROR da VPS não vira contagem", (function () {
    try { lerSaidaDaVps(JSON.stringify({ resultado: "ERROR", erro: "consulta_alunos" })); return false; } catch (e) { return true; }
  })());
  caso("leitor da VPS: saída vazia não vira zero", (function () {
    try { lerSaidaDaVps(""); return false; } catch (e) { return true; }
  })());
}

// --------------------------------------------------------------- a compra

/** Medido em 27/09/2026: a resposta HTTP 500 da confirmação chega, mas o corpo
 *  dela nunca termina de ser lido pelo navegador. Toda leitura que depende da
 *  rede tem prazo, e o prazo vencido vira fato registrado, nunca espera eterna. */
function comPrazo(promessa, ms, valorNoPrazo) {
  return Promise.race([
    promessa,
    new Promise(function (resolver) { setTimeout(function () { resolver(valorNoPrazo); }, ms); }),
  ]);
}

async function textoDaTela(pagina) {
  return pagina.evaluate(function () {
    var form = document.querySelector("form[data-appmax-checkout]");
    return {
      status: (document.querySelector(".status") || {}).textContent || "",
      erro: ((document.querySelector(".erro") || {}).textContent || "").trim(),
      formulario_visivel: !!form && getComputedStyle(form).display !== "none",
    };
  });
}

async function statusDoPedido(pagina, pedido) {
  try {
    return await comPrazo(pagina.evaluate(function (id) {
      return api.get("/pedidos/" + id).then(function (p) { return p.status; });
    }, pedido), 20000, "nao_medido");
  } catch (e) {
    return "nao_medido";
  }
}

async function tentar(pagina, pedido, cartao) {
  await pagina.waitForFunction(function () {
    var botao = document.querySelector("form[data-appmax-checkout] button[type=submit]");
    return botao && !botao.disabled;
  }, null, { timeout: 60000 });
  await pagina.fill("input[name=card-number]", cartao);
  await pagina.fill("input[name=card-holder-name]", TITULAR);
  await pagina.fill("input[inputmode=numeric][autocomplete=off]", DOCUMENTO_DO_TITULAR);
  await pagina.fill("input[name=exp-month]", VALIDADE.mes);
  await pagina.fill("input[name=exp-year]", VALIDADE.ano);
  await pagina.fill("input[name=cvv]", CVV);
  var tokenizacao = pagina
    .waitForResponse(function (r) { return /\/payments\/tokenize$/.test(r.url()); }, { timeout: ESPERA_RESPOSTA_MS })
    .then(function (r) { return r.status(); }, function () { return null; });
  var confirmacao = pagina
    .waitForResponse(function (r) {
      return r.request().method() === "POST" && r.url().indexOf("/pedidos/" + pedido + "/cartao") !== -1;
    }, { timeout: ESPERA_RESPOSTA_MS })
    .then(async function (r) {
      var corpo = {};
      try { corpo = (await comPrazo(r.json(), 10000, null)) || { payment: { reason_code: "corpo_nao_lido" } }; } catch (e) { corpo = {}; }
      return { http: r.status(), pagamento: (corpo.payment && corpo.payment.status) || "", motivo: (corpo.payment && corpo.payment.reason_code) || "" };
    }, function () { return { http: null, pagamento: "", motivo: "sem_resposta_da_api" }; });
  await pagina.click("form[data-appmax-checkout] button[type=submit]");
  var resultado = await confirmacao;
  resultado.tokenizacao_http = await tokenizacao;
  return resultado;
}

async function pixAindaOferecido(contexto) {
  var pagina = await contexto.newPage();
  try {
    await pagina.goto(BASE + "/checkout/" + OFERTA + "/", { waitUntil: "networkidle" });
    return await pagina.evaluate(function () {
      var ligado = JSON.parse(document.getElementById("appmax-pix-enabled").textContent);
      var botao = Array.prototype.find.call(document.querySelectorAll(".metodo button"), function (b) {
        return b.textContent.trim() === "Pix";
      });
      return ligado === true && !!botao && !botao.disabled;
    });
  } catch (e) {
    return false;
  } finally {
    await pagina.close();
  }
}

async function comprar(playwright, navegador, perfil, linha, inicio) {
  var opcoes = perfil === "celular" ? playwright.devices["Pixel 7"] : { viewport: { width: 1366, height: 768 } };
  var contexto = await navegador.newContext(opcoes);
  var pagina = await contexto.newPage();
  var rede = [];
  pagina.on("request", function (r) {
    if (!/^https?:/.test(r.url())) return;
    rede.push(registrarRequisicao(r.url(), r.method(), r.postData() || "", linha.cartao));
  });
  var comeco = Date.now();
  var fato = {
    cartao_final: linha.cartao.slice(-4),
    caso: linha.caso,
    exigido: linha.exigido,
    perfil: perfil,
    inicio_s: Math.round((comeco - inicio) / 1000),
    tentativas: [],
    pix_oferecido: null,
  };
  try {
    await pagina.goto(BASE + "/checkout/" + OFERTA + "/", { waitUntil: "networkidle" });
    var cartaoLigado = await pagina.evaluate(function () {
      return JSON.parse(document.getElementById("appmax-card-enabled").textContent);
    });
    if (cartaoLigado !== true) {
      await contexto.close();
      erro(
        "o cartão Appmax está desligado em " + BASE + " (appmax-card-enabled não é true).\n" +
          "   Religar é a ativação reversível da TAR-703, gesto do mantenedor. Nenhuma compra foi feita."
      );
    }
    await pagina.fill("#name", "Teste Sandbox Appmax");
    await pagina.fill("#email", "e2e-appmax-" + crypto.randomBytes(6).toString("hex") + "@exemplo.test");
    await pagina.fill("#phone", "11999990000");
    await pagina.click(".metodo button[aria-pressed]:has-text('Cartão')");
    await Promise.all([
      pagina.waitForURL(/\/pedido\/[0-9a-f-]{36}\/cartao\/$/, { timeout: 60000 }),
      pagina.click("button.cta"),
    ]);
    fato.pedido = pagina.url().match(/\/pedido\/([0-9a-f-]{36})\/cartao\/$/)[1];
    var scripts = await pagina.$$eval("script[src]", function (s) { return s.map(function (x) { return x.src; }); });
    if (!paginaEmSandbox(scripts)) {
      await contexto.close();
      erro("a página do cartão não carregou o script SANDBOX da Appmax; nenhum cartão foi digitado.");
    }

    fato.tentativas.push(await tentar(pagina, fato.pedido, linha.cartao));
    if (linha.caso === "aprovado") {
      await pagina
        .waitForFunction(function () {
          return (document.querySelector(".status") || {}).textContent === "Pagamento aprovado!";
        }, null, { timeout: ESPERA_APROVACAO_MS })
        .catch(function () {});
    } else {
      await pagina.waitForTimeout(JANELA_DE_OBSERVACAO_MS);
    }
    fato.tela = await textoDaTela(pagina);
    if ((linha.caso === "recusado" || linha.caso === "erro_transacional") && fato.tela.formulario_visivel) {
      fato.tentativas.push(await tentar(pagina, fato.pedido, linha.cartao));
      await pagina.waitForTimeout(JANELA_DE_OBSERVACAO_MS);
    }
    fato.status_final = await statusDoPedido(pagina, fato.pedido);
    if (linha.caso === "indisponivel") fato.pix_oferecido = await pixAindaOferecido(contexto);
  } catch (e) {
    fato.falha_de_navegacao = String(e && e.message ? e.message : e).split("\n")[0].slice(0, 200);
    fato.tela = fato.tela || { status: "", erro: "", formulario_visivel: false };
    fato.status_final = fato.status_final || "nao_medido";
  }
  fato.duracao_s = Math.round((Date.now() - comeco) / 1000);
  fato.rede = rede;
  await contexto.close();
  return fato;
}

async function etapaComprar(selecao) {
  var saidaDados = argumento("dados", "");
  var saidaScript = argumento("script", "");
  if (!saidaDados || !saidaScript) erro("--etapa=comprar exige --dados=<json> e --script=<sh>");
  var playwright;
  try {
    playwright = require("playwright");
  } catch (e) {
    erro("o pacote 'playwright' não está instalado.\n   npm install --no-save playwright@1.62.1 && npx playwright install --with-deps chromium");
  }
  var navegador;
  try {
    navegador = await playwright.chromium.launch(process.env.PAINEL_NAVEGADOR ? { channel: process.env.PAINEL_NAVEGADOR } : {});
  } catch (e) {
    erro("não consegui abrir o navegador: " + e.message + "\n   npx playwright install --with-deps chromium");
  }
  var inicio = Date.now();
  console.log("COMPRAS SANDBOX em " + BASE + "/checkout/" + OFERTA + "/ | " + new Date(inicio).toISOString().slice(0, 16) + "Z");
  var compras = [];
  for (var p = 0; p < selecao.perfis.length; p++) {
    for (var i = 0; i < selecao.linhas.length; i++) {
      var fato = await comprar(playwright, navegador, selecao.perfis[p], selecao.linhas[i], inicio);
      compras.push(fato);
      console.log(
        "  " + fato.perfil + " cartão final " + fato.cartao_final + " (" + fato.caso + "): pedido " +
          (fato.pedido ? resumo(fato.pedido) : "não criado") + ", tentativas " +
          JSON.stringify(fato.tentativas.map(function (t) { return [t.http, t.pagamento]; })) +
          ", pedido " + fato.status_final + (fato.falha_de_navegacao ? ", navegação: " + fato.falha_de_navegacao : "")
      );
    }
  }
  await navegador.close();
  var pedidos = compras.filter(function (c) { return c.pedido; }).map(function (c) { return c.pedido; });
  fs.writeFileSync(saidaDados, JSON.stringify({ inicio_utc: new Date(inicio).toISOString().slice(0, 16) + "Z", base: BASE, compras: compras }), "utf8");
  if (!pedidos.length) erro("nenhum pedido foi criado; não há o que contar na VPS.");
  fs.writeFileSync(saidaScript, scriptDaVps(pedidos.map(resumo)), "utf8");
  console.log("\n" + compras.length + " compras gravadas; " + pedidos.length + " pedidos vão à contagem da VPS.");
}

function etapaConferir(selecao) {
  var entrada = argumento("dados", "");
  if (!entrada) erro("--etapa=conferir exige --dados=<json> da etapa comprar");
  var dados;
  var vps;
  try {
    dados = JSON.parse(fs.readFileSync(entrada, "utf8"));
    vps = lerSaidaDaVps(process.env.SAIDA);
  } catch (e) {
    erro("não consegui ler as duas fontes: " + e.message);
  }
  var esperadas = selecao.linhas.length * selecao.perfis.length;
  caso("seleção: o número de compras gravadas bate com o pedido (" + esperadas + ")", dados.compras.length === esperadas, "gravadas " + dados.compras.length);
  var linhas = [];
  var vazamentos = [];
  var hosts = {};
  dados.compras.forEach(function (compra) {
    compra.rede.forEach(function (r) {
      var chave = r.host + (r.pan || r.cvv ? " (dado do cartão)" : "");
      hosts[chave] = (hosts[chave] || 0) + 1;
      if (r.vazou) vazamentos.push(compra.perfil + " " + compra.cartao_final + ": " + r.metodo + " " + r.host + r.caminho);
    });
    var contagem = compra.pedido ? vps[resumo(compra.pedido)] : null;
    var faltas = compra.falha_de_navegacao ? ["navegação interrompida: " + compra.falha_de_navegacao] : julgar(compra, contagem);
    caso(compra.perfil + " cartão final " + compra.cartao_final + " (" + compra.exigido + ")", faltas.length === 0, faltas.join("; "));
    linhas.push({
      perfil: compra.perfil,
      cartao_final: compra.cartao_final,
      exigido: compra.exigido,
      pedido: compra.pedido ? resumo(compra.pedido) : null,
      inicio_s: compra.inicio_s,
      duracao_s: compra.duracao_s,
      tentativas_api: compra.tentativas,
      pedido_na_tela: compra.status_final,
      tela: compra.tela,
      pix_oferecido: compra.pix_oferecido,
      vps: contagem || null,
      veredito: faltas.length ? "FAIL" : "PASS",
      faltas: faltas,
    });
  });
  caso("rede: número do cartão e código de segurança só foram à tokenização da Appmax", vazamentos.length === 0, vazamentos.join(" | "));
  var evidencia = { inicio_utc: dados.inicio_utc, base: dados.base, rede_por_host: hosts, vazamentos: vazamentos, cartoes: linhas };
  console.log("\nEVIDÊNCIA SANITIZADA\n" + JSON.stringify(evidencia, null, 1));
  if (process.env.GITHUB_STEP_SUMMARY) {
    var md = "## Matriz oficial Appmax sandbox pela tela\n\nInício: " + dados.inicio_utc + " em " + dados.base + "\n\n" +
      "| Perfil | Cartão | Exigido | API | Pedido | Matrículas | Veredito |\n|---|---|---|---|---|---|---|\n";
    linhas.forEach(function (l) {
      md += "| " + l.perfil + " | final " + l.cartao_final + " | " + l.exigido + " | " +
        l.tentativas_api.map(function (t) { return t.http + " " + t.pagamento; }).join(", ") + " | " +
        l.pedido_na_tela + " | " + (l.vps ? l.vps.matriculas.length : "sem contagem") + " | " +
        l.veredito + (l.faltas.length ? ": " + l.faltas.join("; ") : "") + " |\n";
    });
    md += "\n### Rede (requisições por destino)\n\n```json\n" + JSON.stringify(hosts, null, 1) + "\n```\n\n" +
      "Dado do cartão fora da tokenização da Appmax: " + (vazamentos.length ? vazamentos.join("; ") : "nenhum") + "\n\n" +
      "### Evidência completa\n\n```json\n" + JSON.stringify(evidencia) + "\n```\n";
    fs.appendFileSync(process.env.GITHUB_STEP_SUMMARY, md, "utf8");
  }
}

async function principal() {
  if (ETAPA === "auto-teste") {
    autoTeste();
  } else if (ETAPA === "comprar") {
    var selecaoDaCompra = selecaoDaLinhaDeComando();
    autoTeste();
    if (falhas.length) erro("o auto-teste reprovou; nenhuma compra foi feita.");
    await etapaComprar(selecaoDaCompra);
  } else if (ETAPA === "conferir") {
    etapaConferir(selecaoDaLinhaDeComando());
  } else {
    erro("--etapa desconhecida: '" + ETAPA + "' (use auto-teste, comprar ou conferir)");
  }
  console.log("");
  if (falhas.length) {
    console.error("❌ " + falhas.length + " caso(s) FALHARAM (etapa " + ETAPA + ").");
    process.exit(1);
  }
  console.log("✅ appmax_sandbox (etapa " + ETAPA + "): nenhum caso falhou.");
  process.exit(0);
}

principal().catch(function (e) {
  erro("o rito não terminou: " + (e && e.stack ? e.stack : e));
});
