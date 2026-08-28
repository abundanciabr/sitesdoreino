// =============================================================================
// painel/gerar_manifesto.js — valida o livro de ocorrências e MONTA O PAINEL.
//
// O nome ficou do tempo em que ele só escrevia um manifesto. Hoje ele monta a
// página inteira, e o nome não foi trocado de propósito: renomear puxaria três
// arquivos de `ci/` e o `CLAUDE.md` — caminhos CODEOWNERS e arquivo-lei — para
// dentro de um PR que é puro `painel/`, custando um mandato por cosmética.
//
// O QUE ELE ESCREVE (nenhum se edita à mão):
//   painel.html        ← painel.template.html + as REGRAS + o RESUMO, embutidos.
//                        Abrir o painel é UM pedido. Só isto.
//   livro-AAAAMM.js    ← o conteúdo dos registros daquele mês. Buscado só quando
//                        você abre a Memória. Mês fechado nunca mais é reescrito.
//
// POR QUE ASSIM (o incidente que pagou por este desenho): até 27/08/2026 o
// manifesto fazia `document.write` de um <script> por registro. Abrir o painel
// disparava 86 pedidos de uma vez; cada um atravessa a porta da área
// administrativa, que pergunta à identidade quem é você com 2s de paciência.
// Sob a rajada parte estourava, voltava página de erro no lugar do JS, e o
// painel se recusava a abrir — quatro vezes num dia. O conserto seguinte juntou
// tudo num arquivo só (3 pedidos): matou a rajada e deixou o custo de ABRIR
// crescendo com todo o histórico, num livro que recebeu 48 registros num dia.
// Agora o custo de abrir é limitado e não cresce mais: o resumo viaja dentro da
// página, o passado fica em arquivos por mês.
//
// A LINHA QUE NÃO SE CRUZA: só entra no resumo o que NÃO depende do relógio.
// Idade de pedido, vencimento e "o que mudou em 7 dias" continuam sendo contados
// no navegador, ao abrir. Congelar isso no build fossilizaria o frescor — a
// doença que este painel existe para não ter.
//
// Por que em Node e não Python: a validação e a seleção são a MESMA logica.js
// que a página usa. Um validador só, imposto dos dois lados — dois validadores
// separados divergiriam em silêncio (RETROSPECTIVA-FASE-D §2). Quem confere
// isto de FORA, sem reusar este código, é `ci/verificar_painel.py`.
//
// Uso:
//   node painel/gerar_manifesto.js            → valida e (re)escreve os gerados
//   node painel/gerar_manifesto.js --conferir → só confere; sai 1 se desatualizado
//
// Estados (RETROSPECTIVA-FASE-D §1 — ERROR nunca vira PASS):
//   exit 0 = OK · exit 1 = FAIL (registro inválido / gerado desatualizado)
//   exit 2 = ERROR (não consegui medir: arquivo ilegível, pasta ausente…)
// =============================================================================
"use strict";
var fs = require("fs");
var path = require("path");
var vm = require("vm");
var crypto = require("crypto");

var AQUI = __dirname;
var PASTA = path.join(AQUI, "registros");
var TEMPLATE = path.join(AQUI, "painel.template.html");
var SAIDA_PAGINA = path.join(AQUI, "painel.html");
var ARQUIVO_LOGICA = path.join(AQUI, "logica.js");
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
var impressoes = [];
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
  // A impressão digital de cada fonte, para o CARIMBO da geração (abaixo).
  // Sobre o conteúdo normalizado: fim de linha não é conteúdo, e um checkout
  // Windows não pode produzir um carimbo diferente do de um runner Linux.
  impressoes.push(base + "|" + crypto.createHash("sha256")
    .update(semBOM(codigo), "utf8").digest("hex"));
  var lista = sandbox.window.REGISTROS || [];
  if (lista.length !== 1) { problemas.push(nome + ": deve empurrar EXATAMENTE 1 registro (empurrou " + lista.length + ")"); return; }
  var r = lista[0];
  if (r.arquivo !== base) problemas.push(nome + ": campo 'arquivo' ('" + r.arquivo + "') difere do nome do arquivo ('" + base + "')");
  registros.push(r);
});

// A MESMA validação da página. Um contrato, dois guardiões, zero divergência.
problemas = problemas.concat(LOGICA.validarRegistros(registros));
if (problemas.length) falha(problemas);

// -----------------------------------------------------------------------------
// O CARIMBO DA GERAÇÃO — a impressão digital do livro que produziu estes
// arquivos. Determinístico de propósito: mesmo livro, mesmo carimbo, em
// qualquer máquina. Sem relógio e sem número de build, senão dois checkouts do
// mesmo commit gerariam carimbos diferentes e a comparação abaixo viraria ruído.
//
// PARA QUE SERVE: a página carrega o carimbo, e cada arquivo de mês carrega o
// mesmo. Quando um mês é aberto, os dois são comparados. Se diferirem, os
// arquivos vieram de GERAÇÕES DIFERENTES — e isso é uma falha distinta de
// "o arquivo não chegou" ou "o arquivo veio quebrado". É o caso que o
// mantenedor tem de sobra: o repositório mora dentro do OneDrive, e uma
// sincronização pela metade entrega alguns arquivos novos e outros velhos, cada
// um íntegro por si. Sem o carimbo, isso se apresenta como registro faltando —
// e manda procurar defeito onde não há.
// -----------------------------------------------------------------------------
var CARIMBO = crypto
  .createHash("sha256")
  .update(impressoes.join(String.fromCharCode(10)), "utf8")
  .digest("hex")
  .slice(0, 12);

// -----------------------------------------------------------------------------
// O RESUMO: o que a página precisa para desenhar capa e mapa, e nada mais.
// Quem decide o que entra é `logica.js` — as MESMAS regras que a página aplica.
// -----------------------------------------------------------------------------
var resumo = LOGICA.montarResumo(registros);
if (resumo.erro) falha([resumo.erro]);

// -----------------------------------------------------------------------------
// O PASSADO, em arquivos por mês. A chave é a data do NOME do arquivo (que é o
// id, estável e único), e não o campo `quando` — um registro pode narrar um fato
// antigo, e mudar de gaveta depois quebraria a promessa de que mês fechado nunca
// mais é reescrito. É essa promessa que faz o Git parar de crescer com o livro.
// -----------------------------------------------------------------------------
var porMes = {};
registros.forEach(function (r) {
  var m = r.arquivo.slice(0, 4) + "-" + r.arquivo.slice(4, 6);
  (porMes[m] = porMes[m] || []).push(r);
});
var meses = Object.keys(porMes).sort();

// Embutir JSON dentro de uma ilha de script exige fechar UMA porta: a sequência
// que fecha a tag, aparecendo dentro de um texto, encerraria o bloco no meio da
// página. O "<" vira escape unicode; JSON.parse devolve o caractere de volta, e
// o navegador nunca chega a ver uma tag.
function comoTextoJS(valor) {
  return JSON.stringify(JSON.stringify(valor)).replace(/</g, "\\u003c");
}

var AVISO = [
  "// =============================================================================",
  "// GERADO por painel/gerar_manifesto.js — NÃO EDITE À MÃO.",
  "// Para regenerar: node painel/gerar_manifesto.js",
  "// ============================================================================="
];

var escritas = [];
var declaracaoDosMeses = meses.map(function (m) {
  var lista = porMes[m];
  var arquivo = "livro-" + m.replace("-", "") + ".js";
  escritas.push({
    nome: arquivo,
    caminho: path.join(AQUI, arquivo),
    conteudo: AVISO.concat([
      "// O livro de " + m + ": " + lista.length + " registros, um pedido, e só quando",
      "// você pedir. A fonte de verdade continua em painel/registros/, um arquivo",
      "// por ocorrência.",
      "//",
      "// JSON.parse de uma string feita por JSON.stringify — e NÃO concatenação do",
      "// código-fonte dos registros. A diferença não é estilo: concatenando, uma",
      "// aspa errada num registro derruba TODOS os deste mês, porque erro de",
      "// sintaxe não se pega com try/catch. Aqui o escape é por construção.",
      "(function () {",
      "  window.LIVRO = window.LIVRO || {};",
      "  window.LIVRO[" + JSON.stringify(m) + "] = {",
      "    mes: " + JSON.stringify(m) + ",",
      "    carimbo: " + JSON.stringify(CARIMBO) + ",",
      "    registros: JSON.parse(" + comoTextoJS(lista) + ")",
      "  };",
      "})();",
      ""
    ]).join("\n")
  });
  // A página confere a CONTAGEM declarada aqui contra a que chegar, e recusa id
  // repetido. Os ids e o hash de cada registro ficam para o verificador do CI
  // (ci/verificar_painel.py): guardá-los aqui faria esta página crescer com a
  // idade do projeto, que é exatamente o que este desenho existe para impedir.
  return { mes: m, arquivo: arquivo, count: lista.length };
});

// -----------------------------------------------------------------------------
// A PÁGINA: o template + as regras + o resumo, tudo num arquivo só.
// -----------------------------------------------------------------------------
var template, logicaFonte;
// Normaliza os fins de linha do template ANTES de injetar. Sem isto, o
// painel.html gerado herda o que o checkout deu: num clone Windows o Git
// entrega o template em CRLF, num runner Linux em LF — e o mesmo livro
// produzia dois arquivos diferentes. O `--conferir` normaliza os dois lados e
// não acusava, então a divergência viajava em silêncio até alguém comparar
// bytes (foi um teste-guarda de CRLF que a expôs, em 27/08/2026).
// Determinismo é a promessa deste gerador: mesmo livro, mesmos bytes.
try { template = semBOM(fs.readFileSync(TEMPLATE, "utf8")); }
catch (e) { erro("não consegui ler " + TEMPLATE + ": " + e.message); }
try { logicaFonte = fs.readFileSync(ARQUIVO_LOGICA, "utf8"); }
catch (e) { erro("não consegui ler " + ARQUIVO_LOGICA + ": " + e.message); }
if (template.indexOf("__DADOS_DO_PAINEL__") === -1) {
  erro("painel.template.html não tem o marcador __DADOS_DO_PAINEL__ — sem ele a página nasceria sem dados e sem regras.");
}

// Montadas por concatenação para que este arquivo-fonte não contenha, ele
// próprio, uma tag de fechamento solta.
// Medido ANTES de montar o bloco de dados: é ele que a página carimba para
// poder mostrar quanto do orçamento já foi usado.
var bytesResumo = Buffer.byteLength(JSON.stringify(resumo.registros), "utf8");

var ABRE = "<" + "script>";
var FECHA = "<" + "/script>";
var dados = [
  ABRE,
  "/* GERADO — as regras do painel (painel/logica.js), embutidas para que abrir",
  "   custe UM pedido. Edite painel/logica.js, nunca este bloco. */",
  semBOM(logicaFonte).trimEnd(),
  FECHA,
  ABRE,
  "/* GERADO — o resumo: só o que a capa e o mapa desenham. O passado fica nos",
  "   arquivos por mês. Nada aqui depende do relógio — idade de pedido,",
  "   vencimento e o que mudou em 7 dias são contados no SEU navegador, ao",
  "   abrir. Congelar essas contas aqui fossilizaria o frescor. */",
  "var PAINEL = {",
  "  carimbo: " + JSON.stringify(CARIMBO) + ",",
  // Quanto do orçamento já foi usado, para a página poder MOSTRAR o tanque
  // enchendo. Sem isto o teto só se manifesta no dia em que o gerador se
  // recusa a construir — e aí o dono descobre pela porta que não abre, em vez
  // de ver a coisa chegando. `paginaBytes` entra como marcador de LARGURA FIXA
  // e é trocado depois de a página ser medida: se ele mudasse de tamanho ao ser
  // preenchido, o número que ele carrega deixaria de ser o tamanho real.
  "  orcamento: { resumoBytes: " + bytesResumo + ", resumoTeto: " + LOGICA.ORCAMENTO_RESUMO_BYTES +
    ", paginaBytes: __TAMANHO__, paginaTeto: " + LOGICA.ORCAMENTO_PAINEL_BYTES + " },",
  "  livro: { total: " + registros.length + ", meses: " + JSON.stringify(declaracaoDosMeses) + " },",
  "  resumo: JSON.parse(" + comoTextoJS({
    respondidos: resumo.respondidos,
    registros: resumo.registros,
    maisRecenteQuando: resumo.maisRecenteQuando,
    totalNoLivro: resumo.totalNoLivro
  }) + ")",
  "};",
  FECHA
].join("\n");

// Função como substituto: com string, "$&" e afins dentro dos dados virariam
// referências de captura e o painel nasceria corrompido em silêncio.
var pagina = template.replace("__DADOS_DO_PAINEL__", function () { return dados; });

// -----------------------------------------------------------------------------
// O ORÇAMENTO. O gerador RECUSA construir em vez de crescer — a mesma lei do
// TETO_BLOCOS_CAPA, pelo motivo escrito lá: lei escrita não segurou a poda de
// 24/08; gerador que quebra, segura. Estourar não é defeito do painel: é sinal
// de que algo real se acumulou (pedidos sem resposta, entregas sem prova), e a
// resposta certa é olhar o acúmulo, nunca subir o teto.
// -----------------------------------------------------------------------------
// O marcador tem 11 caracteres ("__TAMANHO__"); o número que o substitui é
// preenchido com zeros até 11. Assim o tamanho medido continua sendo o tamanho
// final, byte a byte — um marcador de largura variável faria a página declarar
// um tamanho que ela não tem.
var bytesPagina = Buffer.byteLength(pagina, "utf8");
var tamanhoEmOnze = String(bytesPagina);
while (tamanhoEmOnze.length < 11) tamanhoEmOnze = "0" + tamanhoEmOnze;
if (tamanhoEmOnze.length !== 11) {
  erro("o painel passou de 99.999.999.999 bytes — o marcador de tamanho não cabe mais.");
}
pagina = pagina.replace("__TAMANHO__", tamanhoEmOnze);
var estouros = [];
if (bytesResumo > LOGICA.ORCAMENTO_RESUMO_BYTES) {
  estouros.push("o resumo pesa " + bytesResumo + " bytes e o orçamento é " +
    LOGICA.ORCAMENTO_RESUMO_BYTES + " — veja O QUE está se acumulando na capa antes de pensar no teto.");
}
if (bytesPagina > LOGICA.ORCAMENTO_PAINEL_BYTES) {
  estouros.push("painel.html pesaria " + bytesPagina + " bytes e o orçamento é " +
    LOGICA.ORCAMENTO_PAINEL_BYTES + ".");
}
if (estouros.length) falha(estouros);

escritas.push({ nome: "painel.html", caminho: SAIDA_PAGINA, conteudo: pagina });

// Arquivo de mês que sobrou de uma execução antiga é livro fantasma: sai da
// declaração da página e continua no disco, servido a quem adivinhar o nome.
var esperados = {};
escritas.forEach(function (e) { esperados[e.nome] = true; });
var fantasmas = fs.readdirSync(AQUI).filter(function (n) {
  return /^livro-\d{6}\.js$/.test(n) && !esperados[n];
});

// Fins de linha não são conteúdo: num checkout Windows o git converte o gerado
// para CRLF e a comparação byte a byte reprovava com o livro perfeitamente em
// dia (armadilhas/122). Normalizar os DOIS lados compara o que importa.
function normalizar(texto) { return texto.replace(/\r\n/g, "\n"); }

// Tira a marca de codificação do começo e normaliza os fins de linha. As duas
// coisas juntas porque servem à MESMA promessa: mesmo livro, mesmos bytes, em
// qualquer checkout. Sem isto o Git entrega o template em CRLF num clone
// Windows e em LF num runner Linux, e o painel.html gerado saía diferente nos
// dois — sem ninguém acusar, porque o `--conferir` normaliza os dois lados
// antes de comparar. Quem expôs foi um teste-guarda de CRLF, em 27/08/2026.
// A comparação por `charCodeAt` evita escrever aqui, literalmente, o caractere
// que esta função existe para remover.
function semBOM(texto) {
  return normalizar(texto.charCodeAt(0) === 0xFEFF ? texto.slice(1) : texto);
}

var modoConferir = process.argv.indexOf("--conferir") !== -1;
if (modoConferir) {
  var pendencias = [];
  escritas.forEach(function (e) {
    var atual;
    try { atual = fs.readFileSync(e.caminho, "utf8"); }
    catch (err) { pendencias.push(e.nome + " não existe"); return; }
    if (normalizar(atual) !== normalizar(e.conteudo)) {
      pendencias.push(e.nome + " está DESATUALIZADO em relação a registros/");
    }
  });
  fantasmas.forEach(function (n) {
    pendencias.push(n + " sobrou de uma geração antiga e nenhum mês o reivindica");
  });
  if (pendencias.length) {
    console.error("❌ FAIL: o painel gerado não corresponde ao livro de ocorrências:");
    pendencias.forEach(function (m) { console.error("   - " + m); });
    console.error("   Rode: node painel/gerar_manifesto.js  (e commite o resultado)");
    process.exit(1);
  }
  console.log("✅ painel em dia — " + registros.length + " registros válidos em " +
    meses.length + " mês(es); abrir custa 1 pedido (" + (bytesPagina / 1024).toFixed(1) + " KB).");
  process.exit(0);
}

escritas.forEach(function (e) {
  try { fs.writeFileSync(e.caminho, e.conteudo, "utf8"); }
  catch (err) { erro("não consegui escrever " + e.nome + ": " + err.message); }
});
fantasmas.forEach(function (n) {
  try { fs.unlinkSync(path.join(AQUI, n)); console.log("   removido (mês que não existe mais): " + n); }
  catch (err) { erro("não consegui remover " + n + ": " + err.message); }
});
console.log("✅ painel.html gerado — " + registros.length + " registros válidos em " +
  meses.length + " mês(es).");
console.log("   abrir o painel = 1 pedido (" + (bytesPagina / 1024).toFixed(1) + " KB; resumo de " +
  (bytesResumo / 1024).toFixed(1) + " KB, " + resumo.registros.length + " registros).");
console.log("   o passado espera em: " + declaracaoDosMeses.map(function (m) { return m.arquivo; }).join(", "));
