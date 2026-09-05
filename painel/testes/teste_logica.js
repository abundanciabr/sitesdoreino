#!/usr/bin/env node
// =============================================================================
// painel/testes/teste_logica.js — o teste-guarda da lógica que calcula o painel.
//
// "Quem vigia o vigia da tela": um erro na lógica esconde problema sem ninguém
// mentir. Cada regra abaixo é testada nos DOIS sentidos — aceita o certo e
// RECUSA o errado (RETROSPECTIVA-FASE-D §1: portão que nunca reprovou é portão
// que ninguém sabe se reprova).
//
// Rodar: node painel/testes/teste_logica.js   (exit 0 = verde, 1 = vermelho)
// =============================================================================
"use strict";
var path = require("path");
var LOGICA = require(path.join(__dirname, "..", "logica.js"));

var falhas = [];
function caso(nome, cond) {
  if (cond) console.log("  PASS " + nome);
  else { console.error("  FAIL " + nome); falhas.push(nome); }
}
function reg(sobre) {
  var base = {
    arquivo: "20260826-900-teste", tipo: "nota", quando: "2026-08-26",
    titulo: "t", detalhe: "d", autoridade: "sessao", evidencia: null,
    verificado_em: null, precisa_do_dono: false, responde_a: null,
    gravidade: "info", frente: null, vence_em_dias: null
  };
  Object.keys(sobre || {}).forEach(function (k) { base[k] = sobre[k]; });
  return base;
}
var AGORA = new Date("2026-08-26T15:00:00");

console.log("== validarRegistros ==");
caso("registro completo passa", LOGICA.validarRegistros([reg({})]).length === 0);
caso("campo obrigatório ausente REPROVA", LOGICA.validarRegistros([reg({ titulo: "" })]).length > 0);
caso("tipo desconhecido REPROVA", LOGICA.validarRegistros([reg({ tipo: "invencao" })]).length > 0);
caso("data inválida REPROVA", LOGICA.validarRegistros([reg({ quando: "ontem" })]).length > 0);
caso("HTML no título REPROVA", LOGICA.validarRegistros([reg({ titulo: "oi <b>x</b>" })]).length > 0);
caso("arquivo duplicado REPROVA",
  LOGICA.validarRegistros([reg({}), reg({})]).length > 0);
caso("responde_a inexistente REPROVA",
  LOGICA.validarRegistros([reg({ responde_a: "20990101-001-fantasma" })]).length > 0);
// Compromisso (03/09/2026, degrau 2 do painel de gestão): promessa da semana
// com prazo. Sem prazo não vence, e o que não vence não cobra ninguém.
caso("compromisso com prazo passa", LOGICA.validarRegistros([reg({ tipo: "compromisso", vence_em_dias: 7 })]).length === 0);
caso("compromisso sem prazo REPROVA", LOGICA.validarRegistros([reg({ tipo: "compromisso", vence_em_dias: null })]).length > 0);
caso("compromisso com prazo zero REPROVA", LOGICA.validarRegistros([reg({ tipo: "compromisso", vence_em_dias: 0 })]).length > 0);
// A foto da semana (04/09/2026, degrau 6): medição com "cartao=valor; ...".
caso("foto bem formada numa medição passa", LOGICA.validarRegistros([reg({ tipo: "medicao", foto: "compras-no-mes=3; liberacoes-em-48h=100; latencia-de-decisao=1.5" })]).length === 0);
caso("foto fora de medição REPROVA", LOGICA.validarRegistros([reg({ tipo: "nota", foto: "compras-no-mes=3" })]).length > 0);
caso("foto torta REPROVA", LOGICA.validarRegistros([reg({ tipo: "medicao", foto: "compras no mês: três" })]).length > 0);
caso("foto nula é ausência, passa", LOGICA.validarRegistros([reg({ tipo: "medicao", foto: null })]).length === 0);
// O LABORATÓRIO (05/09/2026, degrau 12): o experimento é uma medição que
// declara a aposta ANTES de saber o resultado, e o resultado é outro registro
// que a fecha. Os quatro campos andam juntos porque um experimento existe para
// ser julgado: hipótese sem métrica não vence nem perde, e métrica sem prazo
// nunca é cobrada.
function experimento(sobre) {
  var base = {
    arquivo: "20260905-901-experimento", tipo: "medicao",
    problema: "ninguém confirma no mesmo dia",
    hipotese: "avisar por mensagem corta a espera pela metade",
    metrica: "liberacoes-em-48h",
    guarda: "se alguém esperar mais de 3 dias, paramos",
    vence_em_dias: 14
  };
  Object.keys(sobre || {}).forEach(function (k) { base[k] = sobre[k]; });
  return reg(base);
}
caso("experimento com os cinco campos passa", LOGICA.validarRegistros([experimento({})]).length === 0);
LOGICA.CAMPOS_DO_EXPERIMENTO.forEach(function (campo) {
  var sem = {}; sem[campo] = null;
  caso("experimento sem '" + campo + "' REPROVA (aposta que ninguém julga depois)",
    LOGICA.validarRegistros([experimento(sem)]).length > 0);
});
caso("experimento sem prazo REPROVA", LOGICA.validarRegistros([experimento({ vence_em_dias: null })]).length > 0);
caso("experimento com prazo zero REPROVA", LOGICA.validarRegistros([experimento({ vence_em_dias: 0 })]).length > 0);
caso("experimento fora de 'medicao' REPROVA", LOGICA.validarRegistros([experimento({ tipo: "nota" })]).length > 0);
caso("metrica que não é nome de cartão REPROVA",
  LOGICA.validarRegistros([experimento({ metrica: "as liberações em 48 horas" })]).length > 0);
caso("medição comum, sem nenhum campo de experimento, continua passando",
  LOGICA.validarRegistros([reg({ tipo: "medicao" })]).length === 0);
caso("resultado com veredito e responde_a passa",
  LOGICA.validarRegistros([experimento({}), reg({
    arquivo: "20260905-902-resultado", tipo: "medicao",
    responde_a: "20260905-901-experimento", veredito: "venceu"
  })]).length === 0);
caso("'não deu para saber' é desfecho legítimo",
  LOGICA.validarRegistros([experimento({}), reg({
    arquivo: "20260905-902-resultado", tipo: "medicao",
    responde_a: "20260905-901-experimento", veredito: "nao-deu-para-saber"
  })]).length === 0);
caso("veredito fora do vocabulário REPROVA",
  LOGICA.validarRegistros([experimento({}), reg({
    arquivo: "20260905-902-resultado", tipo: "medicao",
    responde_a: "20260905-901-experimento", veredito: "meio que deu certo"
  })]).length > 0);
caso("veredito sem responde_a REPROVA (julgamento sem aposta)",
  LOGICA.validarRegistros([reg({
    arquivo: "20260905-902-resultado", tipo: "medicao", veredito: "venceu"
  })]).length > 0);
caso("veredito fora de 'medicao' REPROVA",
  LOGICA.validarRegistros([experimento({}), reg({
    arquivo: "20260905-902-resultado", tipo: "nota",
    responde_a: "20260905-901-experimento", veredito: "venceu"
  })]).length > 0);
// Número repetido no mesmo dia: a corrida entre sessões paralelas (26/08/2026,
// quatro colisões em um dia, entre três sessões). O nome completo continua
// único — o que se perde é o número como referência.
caso("mesmo NÚMERO no mesmo dia, slugs diferentes, REPROVA",
  LOGICA.validarRegistros([
    reg({ arquivo: "20260826-900-um" }), reg({ arquivo: "20260826-900-outro" })
  ]).length > 0);
caso("mesmo número em DIAS diferentes passa (a sequência é por dia)",
  LOGICA.validarRegistros([
    reg({ arquivo: "20260826-900-um" }), reg({ arquivo: "20260827-900-outro", quando: "2026-08-27" })
  ]).length === 0);
caso("as duas colisões HERDADAS de 26/08 continuam passando (não se reescreve registro mergeado)",
  LOGICA.validarRegistros([
    reg({ arquivo: "20260826-036-um" }), reg({ arquivo: "20260826-036-outro" }),
    reg({ arquivo: "20260826-037-um" }), reg({ arquivo: "20260826-037-outro" })
  ]).length === 0);
// A tolerância guarda o TAMANHO do par herdado, não uma licença permanente
// naquele número — senão congelar um par abriria 036 para sempre.
caso("um TERCEIRO registro num par herdado REPROVA (colisão nova, não história)",
  LOGICA.validarRegistros([
    reg({ arquivo: "20260826-036-um" }), reg({ arquivo: "20260826-036-outro" }),
    reg({ arquivo: "20260826-036-terceiro" })
  ]).length > 0);
caso("não-lista vira erro, nunca silêncio", LOGICA.validarRegistros(null).length > 0);

console.log("== verde é conquistado, nunca escrito ==");
caso("verde SEM evidência REPROVA", LOGICA.validarRegistros([reg({ gravidade: "verde" })]).length > 0);
caso("verde com evidência mas SEM verificado_em REPROVA",
  LOGICA.validarRegistros([reg({ gravidade: "verde", evidencia: "x" })]).length > 0);
caso("verde com evidência conferida passa",
  LOGICA.validarRegistros([reg({ gravidade: "verde", evidencia: "x", verificado_em: "2026-08-26" })]).length === 0);

console.log("== a caixa que não consegue esquecer ==");
var pedido = reg({ arquivo: "20260820-001-pedido", tipo: "pendencia", quando: "2026-08-20", precisa_do_dono: true });
caso("pedido sem resposta APARECE na caixa",
  LOGICA.caixaDeEntrada([pedido], AGORA).length === 1);
caso("a idade do pedido é calculada (6 dias)",
  LOGICA.caixaDeEntrada([pedido], AGORA)[0].aguardandoDias === 6);
var resposta = reg({ arquivo: "20260826-002-resposta", tipo: "resposta", responde_a: "20260820-001-pedido" });
caso("pedido RESPONDIDO some da caixa — sem ninguém apagar nada",
  LOGICA.caixaDeEntrada([pedido, resposta], AGORA).length === 0);
var pedidoNovo = reg({ arquivo: "20260825-001-novo", tipo: "pendencia", quando: "2026-08-25", precisa_do_dono: true });
caso("pedido mais VELHO grita primeiro",
  LOGICA.caixaDeEntrada([pedidoNovo, pedido], AGORA)[0].registro.arquivo === "20260820-001-pedido");

// -----------------------------------------------------------------------------
// ...E OS JEITOS DE ELA ESQUECER MESMO ASSIM (auditoria de 26/08/2026).
// A promessa é "uma lista calculada não consegue esquecer". Antes destes casos
// ela conseguia: bastava o campo que alimenta a caixa vir como texto, faltar, ou
// o registro responder a si mesmo — e o gerador aprovava tudo em silêncio.
// Todos REPROVAM na validação: o gerador barra o registro na ENTRADA, em vez de
// a caixa perder o pedido depois, quando ninguém mais está olhando.
// -----------------------------------------------------------------------------
caso("precisa_do_dono como TEXTO 'true' REPROVA (senão o pedido some da caixa)",
  LOGICA.validarRegistros([reg({ precisa_do_dono: "true" })]).length > 0);
caso("precisa_do_dono ESQUECIDO REPROVA",
  LOGICA.validarRegistros([reg({ precisa_do_dono: undefined })]).length > 0);
caso("precisa_do_dono false continua válido (obrigatório é o CAMPO, não o pedido)",
  LOGICA.validarRegistros([reg({ precisa_do_dono: false })]).length === 0);
caso("registro que responde a SI MESMO REPROVA (pedido não se responde sozinho)",
  LOGICA.validarRegistros([reg({ arquivo: "20260826-905-eu", responde_a: "20260826-905-eu", precisa_do_dono: true })]).length > 0);
caso("vence_em_dias como TEXTO '10' REPROVA",
  LOGICA.validarRegistros([reg({ vence_em_dias: "10" })]).length > 0);
caso("evidencia em branco REPROVA (evidência vazia não é evidência)",
  LOGICA.validarRegistros([reg({ evidencia: "   " })]).length > 0);

console.log("== problemas e mudanças ==");
var incendio = reg({ arquivo: "20260826-003-incendio", tipo: "incidente", gravidade: "vermelho" });
caso("incidente vermelho sem resposta está em 'problemas abertos'",
  LOGICA.problemasAbertos([incendio]).length === 1);
var apagado = reg({ arquivo: "20260826-004-apagado", tipo: "resposta", responde_a: "20260826-003-incendio" });
caso("incidente respondido SAI de problemas abertos",
  LOGICA.problemasAbertos([incendio, apagado]).length === 0);
caso("frente âmbar NÃO vira 'problema aberto' (frente tem bloco próprio — um fato, uma casa)",
  LOGICA.problemasAbertos([reg({ tipo: "frente", frente: "curso", gravidade: "ambar" })]).length === 0);
caso("pendência âmbar NÃO vira 'problema aberto' (pendência mora na caixa)",
  LOGICA.problemasAbertos([reg({ tipo: "pendencia", gravidade: "ambar", precisa_do_dono: true })]).length === 0);
caso("mudança de 3 dias atrás entra nos '7 dias'",
  LOGICA.mudancasRecentes([reg({ quando: "2026-08-23" })], AGORA, 7).length === 1);
caso("mudança de 20 dias atrás NÃO entra",
  LOGICA.mudancasRecentes([reg({ quando: "2026-08-06" })], AGORA, 7).length === 0);
// Data no futuro (typo, ou o bug de fuso que a casa já teve) não pode SUMIR da
// capa: fato invisível é pior que fato com data estranha.
caso("registro com data no FUTURO aparece na capa em vez de sumir",
  LOGICA.mudancasRecentes([reg({ quando: "2026-08-28" })], AGORA, 7).length === 1);
caso("...e ele vem em PRIMEIRO, por ser o mais recente",
  LOGICA.mudancasRecentes([reg({ arquivo: "20260823-901-a", quando: "2026-08-23" }),
    reg({ arquivo: "20260828-902-b", quando: "2026-08-28" })], AGORA, 7)[0].arquivo === "20260828-902-b");

console.log("== frentes: o mais recente vence, nada é mantido ==");
var f1 = reg({ arquivo: "20260820-002-f", tipo: "frente", frente: "site", quando: "2026-08-20", titulo: "antigo" });
var f2 = reg({ arquivo: "20260825-002-f", tipo: "frente", frente: "site", quando: "2026-08-25", titulo: "novo" });
var site = LOGICA.estadoDasFrentes([f1, f2]).filter(function (x) { return x.frente === "site"; })[0];
caso("o estado da frente é o registro mais recente", site.registro.titulo === "novo");
caso("frente sem registro aparece como nula (não some)",
  LOGICA.estadoDasFrentes([f1, f2]).filter(function (x) { return x.registro === null; }).length === 4);
caso("tipo 'frente' sem frente válida REPROVA",
  LOGICA.validarRegistros([reg({ tipo: "frente", frente: "outra" })]).length > 0);

console.log("== Meu mapa: cinco capítulos, e o futuro que não se prova ==");
var rumoSite = reg({ arquivo: "20260826-910-rumo", tipo: "rumo", frente: "site", quando: "2026-08-26", titulo: "para onde o site vai" });
var frenteSite = reg({ arquivo: "20260825-910-f", tipo: "frente", frente: "site", quando: "2026-08-25", titulo: "site no ar", gravidade: "verde", evidencia: "curl 200", verificado_em: "2026-08-25" });
caso("o mapa tem sempre os 5 capítulos, mesmo sem registro nenhum",
  LOGICA.meuMapa([], AGORA).length === 5);
caso("a ordem do mapa é a do Roadmap (a fábrica primeiro, vender por último)",
  LOGICA.meuMapa([], AGORA)[0].frente === "fabrica" && LOGICA.meuMapa([], AGORA)[4].frente === "vender");
var capSite = LOGICA.meuMapa([rumoSite, frenteSite], AGORA).filter(function (c) { return c.frente === "site"; })[0];
caso("o capítulo mostra o estado da frente", capSite.estado.titulo === "site no ar");
caso("...e o rumo dela", capSite.rumos.length === 1);
caso("capítulo sem rumo fica SEM rumo (não inventa um)",
  LOGICA.meuMapa([frenteSite], AGORA).filter(function (c) { return c.frente === "site"; })[0].rumos.length === 0);
caso("frente sem registro nenhum aparece com estado nulo — 'não sei', nunca vazio silencioso",
  LOGICA.meuMapa([], AGORA)[0].estado === null);
caso("rumo RESPONDIDO some do mapa — sem ninguém apagar nada",
  LOGICA.meuMapa([rumoSite, reg({ arquivo: "20260827-910-r", tipo: "resposta", responde_a: "20260826-910-rumo" })], AGORA)
    .filter(function (c) { return c.frente === "site"; })[0].rumos.length === 0);
caso("rumo VERDE REPROVA — o futuro não se prova",
  LOGICA.validarRegistros([reg({ tipo: "rumo", frente: "site", gravidade: "verde", evidencia: "x", verificado_em: "2026-08-26" })]).length > 0);
caso("rumo SEM frente REPROVA (rumo sem capítulo não tem onde morar)",
  LOGICA.validarRegistros([reg({ tipo: "rumo" })]).length > 0);
caso("frente inventada REPROVA em qualquer registro, não só nos de tipo 'frente'",
  LOGICA.validarRegistros([reg({ tipo: "nota", frente: "marketing" })]).length > 0);
caso("etiqueta de frente válida numa nota comum passa",
  LOGICA.validarRegistros([reg({ tipo: "nota", frente: "curso" })]).length === 0);
caso("rumo NÃO vira 'problema aberto' (ele mora no mapa — um fato, uma casa)",
  LOGICA.problemasAbertos([reg({ tipo: "rumo", frente: "curso", gravidade: "ambar" })]).length === 0);
caso("o pedido do dono aparece no capítulo da frente dele",
  LOGICA.meuMapa([reg({ arquivo: "20260820-910-p", tipo: "pendencia", frente: "vender", quando: "2026-08-20", precisa_do_dono: true })], AGORA)
    .filter(function (c) { return c.frente === "vender"; })[0].esperando.length === 1);
caso("o resumo do mapa é contado, nunca escrito",
  LOGICA.resumoDoMapa([rumoSite, frenteSite], AGORA).comProvaConferida === 1 &&
  LOGICA.resumoDoMapa([rumoSite, frenteSite], AGORA).semRumo === 4);

console.log("== frescor computado ==");
var vencido = reg({ arquivo: "20260810-001-v", quando: "2026-08-10", vence_em_dias: 7 });
caso("registro vencido é DENUNCIADO", LOGICA.frescor([vencido], AGORA).vencidos.length === 1);
caso("registro dentro do prazo não é",
  LOGICA.frescor([reg({ quando: "2026-08-24", vence_em_dias: 7 })], AGORA).vencidos.length === 0);
caso("o livro parado há N dias é medido",
  LOGICA.frescor([reg({ quando: "2026-08-20" })], AGORA).livroParadoHaDias === 6);

console.log("== dito, mas não comprovado ==");
caso("entrega sem evidência conferida é marcada",
  LOGICA.naoComprovados([reg({ tipo: "entrega" })]).length === 1);
caso("entrega com evidência conferida NÃO é",
  LOGICA.naoComprovados([reg({ tipo: "entrega", evidencia: "x", verificado_em: "2026-08-26" })]).length === 0);

console.log("== a capa: calculada e com teto ==");
var capaOk = LOGICA.capa([pedido, incendio, f1], AGORA);
caso("capa normal constrói sem erro", capaOk.erro === null && capaOk.blocos.length >= 3);
caso("o bloco 'Precisa de você' vem PRIMEIRO (caixa antes do placar)",
  capaOk.blocos[0].id === "caixa");
// Vermelho→verde do teto: o cenário cheio gera os 6 blocos possíveis e AINDA
// constrói; o MESMO cenário com o teto apertado tem que RECUSAR — prova de que
// a recusa dispara de verdade, não é código morto.
var regsCheios = [pedido, incendio, vencido, reg({ tipo: "entrega", arquivo: "20260826-005-e" }), f1];
var capaCheia = LOGICA.capa(regsCheios, AGORA);
caso("cenário cheio usa os 6 blocos e ainda constrói (teto real = " + LOGICA.TETO_BLOCOS_CAPA + ")",
  capaCheia.erro === null && capaCheia.blocos.length === 6);
var capaRecusada = LOGICA._capaComTeto(regsCheios, AGORA, 2);
caso("acima do teto a capa se RECUSA a construir e diz o porquê",
  capaRecusada.erro !== null && capaRecusada.blocos === null && capaRecusada.erro.indexOf("teto") !== -1);


// =============================================================================
// O RESUMO — a peça que faz abrir o painel custar UM pedido (27/08/2026).
//
// A propriedade que precisa ser verdade, e que estes casos medem: **a capa e o
// mapa calculados do RESUMO são idênticos aos calculados do livro INTEIRO.**
// Se algum dia deixarem de ser, o painel passa a mostrar menos do que existe —
// e mostrar menos, sem avisar, é a única coisa que este painel não pode fazer.
// =============================================================================
console.log("== o resumo: um pedido, sem perder nada da capa ==");

// Um livro grande o bastante para o resumo ser mesmo um recorte, com todas as
// formas que a capa e o mapa conhecem.
var livroGrande = [];
for (var i = 1; i <= 60; i++) {
  var num = ("00" + i).slice(-3);
  livroGrande.push(reg({
    arquivo: "20260801-" + num + "-antigo" + i,
    quando: "2026-08-01",
    tipo: (i % 3 === 0) ? "entrega" : "nota",
    evidencia: (i % 2 === 0) ? "prova" : null,
    verificado_em: (i % 2 === 0) ? "2026-08-01" : null
  }));
}
livroGrande.push(pedido);                                   // precisa_do_dono, sem resposta
livroGrande.push(incendio);                                 // vermelho aberto
livroGrande.push(f1);                                       // estado de frente
livroGrande.push(reg({ arquivo: "20260826-090-rumo", tipo: "rumo", frente: "site", gravidade: "info" }));
// Um pedido ANTIGO cuja resposta é recente: é o caso que decide se o mapa de
// respostas precisa viajar calculado sobre o livro inteiro.
livroGrande.push(reg({ arquivo: "20260801-900-pedido-velho", quando: "2026-08-01", precisa_do_dono: true }));
livroGrande.push(reg({ arquivo: "20260826-091-resposta", responde_a: "20260801-900-pedido-velho" }));

var resumo = LOGICA.montarResumo(livroGrande);
caso("montarResumo constrói sem erro", resumo.erro === null);
caso("o resumo é MENOR que o livro (é um recorte de verdade)",
  resumo.registros.length > 0 && resumo.registros.length < livroGrande.length);
caso("o total do livro viaja junto (o rodapé conta o livro, não o recorte)",
  resumo.totalNoLivro === livroGrande.length);

// A PROVA CENTRAL. Mesmo relógio, mesmas regras, fontes diferentes.
var capaCheia2 = LOGICA.capa(livroGrande, AGORA);
var capaResumo = LOGICA.capa(resumo.registros, AGORA, resumo.respondidos);
caso("a capa do resumo tem os MESMOS blocos que a do livro inteiro",
  capaResumo.erro === null && capaCheia2.erro === null &&
  capaResumo.blocos.map(function (b) { return b.id; }).join(",") ===
  capaCheia2.blocos.map(function (b) { return b.id; }).join(","));
caso("...com a MESMA contagem em cada bloco",
  capaResumo.blocos.every(function (b, k) { return b.itens.length === capaCheia2.blocos[k].itens.length; }));
caso("...e exatamente os MESMOS registros na caixa 'Precisa de você'",
  JSON.stringify(LOGICA.caixaDeEntrada(resumo.registros, AGORA, resumo.respondidos)
    .map(function (x) { return x.registro.arquivo; })) ===
  JSON.stringify(LOGICA.caixaDeEntrada(livroGrande, AGORA).map(function (x) { return x.registro.arquivo; })));

var mapaCheio = LOGICA.meuMapa(livroGrande, AGORA);
var mapaResumo = LOGICA.meuMapa(resumo.registros, AGORA, resumo.respondidos);
caso("o mapa do resumo tem o mesmo estado e os mesmos rumos por capítulo",
  mapaResumo.every(function (c, k) {
    var o = mapaCheio[k];
    return c.frente === o.frente &&
      ((c.estado && o.estado) ? c.estado.arquivo === o.estado.arquivo : c.estado === o.estado) &&
      c.rumos.length === o.rumos.length;
  }));

// O caso que o mapa de respostas existe para cobrir: sem ele, um pedido cuja
// resposta ficou fora do recorte voltaria a aparecer como aberto — a caixa
// "Precisa de você" mentiria de novo, que é a doença do H18 por dentro da cura.
var semMapa = LOGICA.caixaDeEntrada(resumo.registros, AGORA).length;
var comMapa = LOGICA.caixaDeEntrada(resumo.registros, AGORA, resumo.respondidos).length;
caso("pedido já respondido NÃO reaparece na caixa (o mapa de respostas viaja junto)",
  comMapa === LOGICA.caixaDeEntrada(livroGrande, AGORA).length && comMapa <= semMapa);

// O relógio NÃO pode ter entrado no resumo: ele é montado uma vez, no build, e
// lido meses depois. Congelar idade ou vencimento ali fossilizaria o frescor.
var resumoA = LOGICA.montarResumo(livroGrande);
var resumoB = LOGICA.montarResumo(livroGrande);
caso("montarResumo é determinístico (mesmo livro → mesmo resumo, sem relógio dentro)",
  JSON.stringify(resumoA) === JSON.stringify(resumoB));
caso("nenhum campo de idade/vencimento foi congelado no resumo",
  JSON.stringify(resumoA.registros).indexOf("aguardandoDias") === -1);

// Os que viajam só como título continuam sendo registros VÁLIDOS: a página os
// desenha com as mesmas regras, e um campo obrigatório faltando derrubaria a
// validação de quem tem o livro todo em mãos.
var soTitulo = resumo.registros.filter(function (r) { return r._so_titulo; });
caso("há registros que viajam só como título (é isso que segura o orçamento)", soTitulo.length > 0);
// A validação inteira não roda sobre um recorte de propósito (um `responde_a`
// cujo alvo ficou de fora acusaria falso). O que importa aqui é que o corte não
// tenha comido nenhum campo OBRIGATÓRIO — inclusive o `detalhe`, que continua
// não-vazio porque passa a dizer onde o texto está.
var OBRIGATORIOS_NA_PAGINA = ["arquivo", "tipo", "quando", "titulo", "detalhe", "autoridade", "gravidade"];
caso("...e nenhum campo obrigatório se perdeu no corte",
  soTitulo.every(function (r) {
    return OBRIGATORIOS_NA_PAGINA.every(function (c) {
      return typeof r[c] === "string" && r[c].trim() !== "";
    }) && typeof r.precisa_do_dono === "boolean";
  }));
caso("...e o texto que ficou no lugar diz ONDE ler o original",
  soTitulo.every(function (r) { return r.detalhe.indexOf("Memória") !== -1; }));
caso("...e é possível saber que o texto ficou para trás", soTitulo.every(function (r) { return r._so_titulo === true; }));

console.log("== a fila de decisão: o que um pedido precisa dizer ==");
// Os quatro campos são OPCIONAIS — torná-los obrigatórios reprovaria todo
// pedido antigo e obrigaria a reescrever o passado, a única coisa que este
// livro proíbe acima de tudo. Mas quando vierem, vêm certos.
var pedidoCompleto = reg({
  arquivo: "20260826-100-pedido-completo", precisa_do_dono: true,
  se_eu_nao_decidir: "a frente fica parada", recomendacao: "escolha a primeira",
  reversivel: true, impacto: "alto"
});
caso("pedido com os quatro campos da decisão é válido",
  LOGICA.validarRegistros([pedidoCompleto]).length === 0);
caso("pedido SEM eles continua válido (o passado não é reescrito)",
  LOGICA.validarRegistros([reg({ arquivo: "20260826-101-sem", precisa_do_dono: true })]).length === 0);

// O caso que motiva o tipo estrito, e não é preciosismo: em JavaScript a string
// "false" é VERDADEIRA. Um `reversivel: "false"` escrito com aspas diria ao dono
// que dá para voltar atrás numa decisão que não desfaz — a mentira mais cara que
// esta ficha pode contar. Mesma família do `precisa_do_dono` com aspas, que fazia
// um pedido sumir da caixa em silêncio (auditoria de 26/08/2026).
var comAspas = LOGICA.validarRegistros([reg({
  arquivo: "20260826-102-aspas", precisa_do_dono: true, reversivel: "false"
})]);
caso("'reversivel' escrito como TEXTO reprova", comAspas.length === 1);
caso("...e a mensagem explica por que isso importa",
  comAspas[0].indexOf("aspas") !== -1);

caso("'impacto' fora do vocabulário reprova",
  LOGICA.validarRegistros([reg({
    arquivo: "20260826-103-impacto", precisa_do_dono: true, impacto: "medio-alto"
  })]).length === 1);
caso("...e os três degraus válidos passam",
  LOGICA.IMPACTOS.every(function (i) {
    return LOGICA.validarRegistros([reg({
      arquivo: "20260826-104-i", precisa_do_dono: true, impacto: i
    })]).length === 0;
  }));

// A contradição que faria o texto se perder: um pedido descreve o custo de não
// decidir e não é para o dono. Ou o texto está no registro errado, ou o
// `precisa_do_dono` ficou false por engano — e com false ele nunca aparece na
// caixa. Nos dois casos, o trabalho de escrever a decisão vai para o lixo.
var contradicao = LOGICA.validarRegistros([reg({
  arquivo: "20260826-105-contradicao", precisa_do_dono: false,
  se_eu_nao_decidir: "nada acontece"
})]);
caso("campo de decisão com precisa_do_dono FALSE reprova", contradicao.length === 1);
caso("...dizendo que o texto se perderia", contradicao[0].indexOf("perderia") !== -1);

// Os campos precisam SOBREVIVER ao corte do resumo. Um pedido da caixa que
// viajasse sem eles apareceria como "não sei o que acontece" tendo a resposta
// escrita no livro — pior do que não ter resposta nenhuma.
var livroComPedido = [];
for (var d = 1; d <= 40; d++) {
  livroComPedido.push(reg({ arquivo: "20260801-" + ("00" + d).slice(-3) + "-enche", quando: "2026-08-01" }));
}
livroComPedido.push(pedidoCompleto);
livroComPedido.push(f1);
var resumoComPedido = LOGICA.montarResumo(livroComPedido);
var naCaixa = LOGICA.caixaDeEntrada(resumoComPedido.registros, AGORA, resumoComPedido.respondidos);
caso("o pedido chega à caixa pelo resumo", naCaixa.length === 1);
caso("...com os quatro campos da decisão intactos",
  naCaixa[0].registro.se_eu_nao_decidir === "a frente fica parada" &&
  naCaixa[0].registro.recomendacao === "escolha a primeira" &&
  naCaixa[0].registro.reversivel === true &&
  naCaixa[0].registro.impacto === "alto");


console.log("== posso confiar nisto? (a quinta pergunta) ==");
// Só `entrega` e `medicao` AFIRMAM algo sobre o mundo e podem ser cobradas por
// prova. Uma `nota` ou uma `decisao` não afirmam que algo funciona — contá-las
// aqui inventaria um denominador maior e faria a cobertura parecer pior do que é.
var livroDeConfianca = [
  reg({ arquivo: "20260826-200-e1", tipo: "entrega", evidencia: "url", verificado_em: "2026-08-26" }),
  reg({ arquivo: "20260826-201-e2", tipo: "entrega", evidencia: "url", verificado_em: "2026-08-26" }),
  reg({ arquivo: "20260826-202-e3", tipo: "entrega", evidencia: null, verificado_em: null }),
  reg({ arquivo: "20260826-203-m1", tipo: "medicao", evidencia: "cmd", verificado_em: "2026-08-26" }),
  reg({ arquivo: "20260826-204-nota", tipo: "nota" }),
  reg({ arquivo: "20260826-205-dec", tipo: "decisao" })
];
var c = LOGICA.confianca(livroDeConfianca);
caso("conta só o que AFIRMA (entrega e medicao), não o livro inteiro", c.afirmacoes === 4);
caso("...e separa quem tem prova conferida", c.comProvaConferida === 3);
caso("...nomeando quem não tem (contagem sozinha não manda procurar)",
  c.semProva.length === 1 && c.semProva[0].arquivo === "20260826-202-e3");

// O PLACAR DE CALIBRAÇÃO: promessa × entrega. Rumo cumprido é rumo com uma
// resposta apontando para ele — a MESMA mecânica da caixa, e não uma segunda
// definição de "cumprido" que pudesse divergir.
var comRumos = [
  reg({ arquivo: "20260801-300-rumo-a", tipo: "rumo", frente: "site", quando: "2026-08-01", gravidade: "info" }),
  reg({ arquivo: "20260804-301-fecha-a", responde_a: "20260801-300-rumo-a", quando: "2026-08-04" }),
  reg({ arquivo: "20260801-302-rumo-b", tipo: "rumo", frente: "curso", quando: "2026-08-01", gravidade: "info" }),
  reg({ arquivo: "20260802-303-fecha-b", responde_a: "20260801-302-rumo-b", quando: "2026-08-02" }),
  reg({ arquivo: "20260801-304-rumo-aberto", tipo: "rumo", frente: "vender", quando: "2026-08-01", gravidade: "info" })
];
var cal = LOGICA.confianca(comRumos);
caso("conta os rumos cumpridos e os abertos", cal.rumosCumpridos === 2 && cal.rumosAbertos === 1);
caso("mede quantos dias do prometer ao cumprir",
  cal.maisRapido.dias === 1 && cal.maisDevagar.dias === 3);
caso("...e devolve a mediana", cal.medianaDeDias === 1);

// A dispersão importa: uma média sozinha esconderia um rumo cumprido em 1 dia e
// outro em 90. O dono precisa ver os dois extremos para julgar.
caso("o mais rápido e o mais devagar vêm nomeados",
  cal.maisRapido.rumo === "20260801-302-rumo-b" && cal.maisDevagar.rumo === "20260801-300-rumo-a");

// Livro sem rumo cumprido não pode inventar um placar. "Não dá para dizer nada"
// é resposta; zero seria afirmar que ninguém entrega.
var semCal = LOGICA.confianca([reg({ arquivo: "20260826-400-x", tipo: "nota" })]);
caso("sem rumo cumprido, a mediana é NULA e não zero",
  semCal.rumosCumpridos === 0 && semCal.medianaDeDias === null && semCal.maisRapido === null);

// E ela precisa VIAJAR no resumo já calculada: refeita no navegador sobre o
// recorte, daria um número errado com cara de certo.
var resumoConf = LOGICA.montarResumo(livroDeConfianca.concat([f1]));
caso("a confiança viaja no resumo, contada sobre o livro inteiro",
  resumoConf.confianca.afirmacoes === 4 && resumoConf.confianca.comProvaConferida === 3);
caso("...e o resumo é MENOR que o livro (então recontá-la lá daria errado)",
  resumoConf.registros.length <= livroDeConfianca.length + 1);

// ===========================================================================
// "ATENÇÃO AGORA" TEM TETO DE TEXTO — e o corte é de texto, nunca de fato
// ===========================================================================
// Medido em 02/09/2026: o resumo tinha 11 bytes de folga no orçamento de 150 KB,
// e 49 KB dele eram incidentes abertos. Um incidente quase nunca ganha registro
// de resposta (o conserto vira uma ENTREGA), então ele fica em "Atenção agora"
// para sempre — um bloco que só cresce dentro de um orçamento que não cresce.
//
// Os quatro casos abaixo travam as quatro coisas que a cura precisa ser: ela
// corta TEXTO, não corta FATO, escolhe pelos mais RECENTES, e tem dentes.
console.log("== teto de texto de Atenção agora ==");

var TETO = LOGICA.PROBLEMAS_COM_DETALHE;
var muitosProblemas = [];
for (var p = 0; p < TETO + 8; p++) {
  // Dias diferentes, do mais antigo para o mais novo: o índice alto é o recente.
  var dia = String(p + 1);
  if (dia.length < 2) dia = "0" + dia;
  muitosProblemas.push(reg({
    arquivo: "202608" + dia + "-70" + (p % 10) + "-problema-" + p,
    tipo: "incidente", quando: "2026-08-" + dia,
    // Gravidade alternada de propósito: a ordem do BLOCO é por gravidade, e o
    // teto tem de escolher por DATA. Com todos vermelhos, um teto que cortasse
    // pela ordem do bloco passaria neste teste sem merecer.
    gravidade: (p % 2 === 0) ? "vermelho" : "ambar",
    titulo: "problema " + p,
    detalhe: "um paragrafo bem comprido ".repeat(20)
  }));
}
var resumoProb = LOGICA.montarResumo(muitosProblemas);
caso("montarResumo constrói com a pilha de problemas", resumoProb.erro === null);

// 1. NENHUM FATO SOME. O bloco continua listando todos, e o cabeçalho conta.
var noResumo = {};
resumoProb.registros.forEach(function (r) { noResumo[r.arquivo] = r; });
caso("nenhum problema aberto some do resumo",
  muitosProblemas.every(function (r) { return !!noResumo[r.arquivo]; }));

// 2. O TEXTO É QUE TEM TETO.
var comTexto = resumoProb.registros.filter(function (r) { return !r._so_titulo; });
caso("o texto completo para no teto (não cresce com a pilha)",
  comTexto.length <= TETO);

// 3. QUEM FICA COM O TEXTO SÃO OS MAIS RECENTES — não os mais graves nem os
//    mais velhos, que é o que a ordem do bloco entregaria de graça.
var maisNovo = muitosProblemas[muitosProblemas.length - 1].arquivo;
var maisVelho = muitosProblemas[0].arquivo;
caso("o problema mais RECENTE mantém o texto", !noResumo[maisNovo]._so_titulo);
caso("o mais ANTIGO viaja só como título", noResumo[maisVelho]._so_titulo === true);
caso("...e o título dele continua lá, com a gravidade, para o bloco poder desenhá-lo",
  noResumo[maisVelho].titulo === "problema 0" && noResumo[maisVelho].gravidade === "vermelho");

// 4. O GUARDA TEM DENTES, e esta é a asserção que mede o motivo de tudo isto:
//    depois do teto, cada problema aberto a mais custa um TÍTULO, não um
//    parágrafo. É o que transforma um bloco que crescia sem limite num bloco
//    com peso previsível. O detalhe fabricado acima tem ~500 letras, então um
//    registro inteiro passa de 600 bytes e um título fica bem abaixo de 400.
function pesoDoResumo(livro) {
  return JSON.stringify(LOGICA.montarResumo(livro).registros).length;
}
var pesoBase = pesoDoResumo(muitosProblemas.slice(0, TETO + 2));
var pesoCheio = pesoDoResumo(muitosProblemas);
var aMais = muitosProblemas.length - (TETO + 2);
caso("passado o teto, cada problema a mais pesa um título e não um parágrafo",
  (pesoCheio - pesoBase) / aMais < 400);


// ---------------------------------------------------------------------------
// O TETO DE TEXTO DA CAIXA "Precisa de você" (TAR-119, 04/09/2026).
//
// Medido no dia: o resumo estava em 137,1 KB dos 150 KB do orçamento (91,4%), e
// a caixa era a ÚNICA fonte de texto completo SEM teto nenhum — dez pedidos
// abertos, 22,4 KB, um parágrafo inteiro por pedido. E ela não encolhe sozinha:
// só o dono a esvazia, respondendo. Bloco que só ele pode encolher, dentro de um
// orçamento que não cresce, tem data marcada.
//
// Os seis casos travam as seis coisas que a cura precisa ser: ela corta TEXTO,
// não corta FATO, não deixa ninguém cair fora do resumo, guarda a FICHA DA
// DECISÃO de quem foi cortado, escolhe pelos mais RECENTES, e tem dentes.
console.log("== teto de texto de Precisa de você ==");

var TETO_CAIXA = LOGICA.CAIXA_COM_DETALHE;
caso("a caixa tem um teto de TEXTO declarado", typeof TETO_CAIXA === "number" && TETO_CAIXA > 0);

// Os pedidos ficam em AGOSTO e, depois deles, TRINTA registros de SETEMBRO. O
// enchimento tem de ser desse tamanho por dois motivos, e o segundo só apareceu
// quando o guarda foi mutado de propósito (04/09/2026):
//   1. sem ele os pedidos seriam os mais recentes do livro e ganhariam texto por
//      `RECENTES_COM_DETALHE` — o teto da caixa passaria sem ser exercido;
//   2. `RECENTES_NO_RESUMO` são 30, e com um livro menor que isso TODO registro
//      chega ao resumo pela porta dos recentes. A primeira versão deste teste
//      tinha 24 registros, e por isso NÃO pegou a mutação que apagava a linha
//      `marcar(apenasTitulo, blocos.caixa)` — o pedido cortado continuava
//      aparecendo, carregado por outra porta. Trinta empurra os pedidos para
//      fora dos recentes e deixa a caixa como única porta deles.
var muitosPedidos = [];
for (var q = 0; q < TETO_CAIXA + 8; q++) {
  var diaP = String(q + 1);
  if (diaP.length < 2) diaP = "0" + diaP;
  muitosPedidos.push(reg({
    arquivo: "202608" + diaP + "-80" + (q % 10) + "-pedido-" + q,
    tipo: "pendencia", quando: "2026-08-" + diaP,
    titulo: "pedido " + q,
    precisa_do_dono: true,
    // `frente: null` de propósito: um pedido sem frente NÃO aparece no Meu mapa,
    // então ele só chega ao resumo se a própria caixa o levar. É este registro
    // que descobre se o corte fez alguém sumir em vez de encolher.
    frente: null,
    se_eu_nao_decidir: "a frente fica parada", recomendacao: "escolha a primeira",
    reversivel: true, impacto: "alto",
    detalhe: "um paragrafo bem comprido ".repeat(60)
  }));
}
var enchimento = [];
for (var w = 0; w < 30; w++) {
  var diaW = String(w + 1);
  if (diaW.length < 2) diaW = "0" + diaW;
  enchimento.push(reg({
    arquivo: "202609" + diaW + "-81" + (w % 10) + "-nota-" + w,
    tipo: "nota", quando: "2026-09-" + diaW, titulo: "nota " + w,
    detalhe: "texto qualquer de enchimento "
  }));
}
var livroCaixa = muitosPedidos.concat(enchimento);
var resumoCaixa = LOGICA.montarResumo(livroCaixa);
caso("montarResumo constrói com a pilha de pedidos", resumoCaixa.erro === null);

var naCaixa = {};
resumoCaixa.registros.forEach(function (r) { naCaixa[r.arquivo] = r; });

// 1. NENHUM FATO SOME. Este é o caso que a caixa exige e o bloco de problemas
//    não exigia: pedido sem frente não tem segunda porta para o resumo.
caso("nenhum pedido aberto some do resumo",
  muitosPedidos.every(function (r) { return !!naCaixa[r.arquivo]; }));
caso("...e a caixa calculada do resumo tem a MESMA contagem da do livro inteiro",
  LOGICA.caixaDeEntrada(resumoCaixa.registros, AGORA, resumoCaixa.respondidos).length ===
  LOGICA.caixaDeEntrada(livroCaixa, AGORA).length);

// 2. O TEXTO É QUE TEM TETO.
var pedidosComTexto = muitosPedidos.filter(function (r) { return naCaixa[r.arquivo] && !naCaixa[r.arquivo]._so_titulo; });
caso("o texto completo dos pedidos para no teto (não cresce com a pilha)",
  pedidosComTexto.length <= TETO_CAIXA);

// 3. QUEM FICA COM O TEXTO SÃO OS MAIS RECENTES — não os do topo do bloco, que
//    é ordenado do mais VELHO para o mais novo ("pedido velho grita mais").
//    Quem cortasse pela ordem do bloco acertaria a contagem e erraria a escolha.
var pedidoMaisNovo = muitosPedidos[muitosPedidos.length - 1].arquivo;
var pedidoMaisVelho = muitosPedidos[0].arquivo;
caso("o pedido mais RECENTE mantém o texto", !naCaixa[pedidoMaisNovo]._so_titulo);
caso("o mais ANTIGO viaja só como título", naCaixa[pedidoMaisVelho]._so_titulo === true);

// 4. A FICHA DA DECISÃO SOBREVIVE AO CORTE. Sem ela o pedido cortado viraria
//    uma linha que não dá para decidir — e aí o corte teria comido o fato.
caso("o pedido cortado continua DECIDÍVEL (os quatro campos vêm junto)",
  ["se_eu_nao_decidir", "recomendacao", "reversivel", "impacto"].every(function (c) {
    return naCaixa[pedidoMaisVelho][c] !== undefined;
  }));
caso("...e o texto que ficou no lugar diz ONDE ler o original",
  naCaixa[pedidoMaisVelho].detalhe.indexOf("Memória") !== -1);

// 5. O GUARDA TEM DENTES. O detalhe fabricado acima tem ~1560 letras, então um
//    pedido inteiro passa de 1900 bytes; um título com a ficha fica abaixo de
//    800. Sem o teto, cada pedido a mais custaria o parágrafo inteiro.
var pesoBaseCaixa = pesoDoResumo(muitosPedidos.slice(0, TETO_CAIXA + 2).concat(enchimento));
var pesoCheioCaixa = pesoDoResumo(livroCaixa);
var pedidosAMais = muitosPedidos.length - (TETO_CAIXA + 2);
caso("passado o teto, cada pedido a mais pesa um título e não um parágrafo",
  (pesoCheioCaixa - pesoBaseCaixa) / pedidosAMais < 800);

console.log("");
if (falhas.length) {
  console.error("❌ " + falhas.length + " caso(s) FALHARAM. A lógica do painel NÃO está confiável.");
  process.exit(1);
}
console.log("✅ teste_logica: todos os casos passaram.");
