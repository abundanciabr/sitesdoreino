// =============================================================================
// painel/logica.js — as regras que calculam TODAS as vistas do painel.
//
// Pura de propósito: nenhum acesso a DOM, a rede ou a relógio aqui dentro —
// quem chama passa os registros e o "agora". É isso que permite o teste-guarda
// (testes/teste_logica.js) rodar em Node, e é o teste que impede esta lógica
// de esconder problema sem ninguém mentir (achado "quem vigia o vigia" das
// consultorias — docs/paineis/VEREDITO-DAS-CONSULTORIAS.html).
//
// Regra de ouro do arquivo: estado NUNCA é lido de um campo "status" escrito
// por alguém — estado é sempre CALCULADO dos registros (pendência aberta =
// pedido sem resposta; verde = evidência conferida; velho = data comparada ao
// relógio). Ver painel/LEIA-ME.md.
// =============================================================================
(function (raiz) {
  "use strict";

  var TIPOS = ["decisao", "pendencia", "resposta", "entrega", "incidente", "medicao", "frente", "nota"];
  var GRAVIDADES = ["vermelho", "ambar", "info", "verde"];
  var AUTORIDADES = ["mantenedor", "github", "sonda", "rito", "sessao"];
  var FRENTES = ["site", "comunidade", "curso", "vender", "fabrica"];
  var TETO_BLOCOS_CAPA = 6; // Opus: "gerador que quebra, segura" — lei escrita não segurou a poda de 24/08.

  var OBRIGATORIOS = ["arquivo", "tipo", "quando", "titulo", "detalhe", "autoridade", "gravidade"];

  function ehDataValida(s) {
    if (typeof s !== "string") return false;
    var m = /^(\d{4})-(\d{2})-(\d{2})(T.*)?$/.exec(s);
    if (!m) return false;
    var d = new Date(s.length === 10 ? s + "T12:00:00" : s);
    return !isNaN(d.getTime());
  }

  function paraData(s) {
    return new Date(s.length === 10 ? s + "T12:00:00" : s);
  }

  function diasEntre(deIso, ateData) {
    return Math.floor((ateData.getTime() - paraData(deIso).getTime()) / 86400000);
  }

  // ---------------------------------------------------------------------------
  // Validação — o mesmo contrato do gerar_manifesto.py, imposto dos dois lados.
  // Devolve lista de erros (vazia = válido). ERROR nunca vira PASS: quem chamar
  // com erros não-vazios NÃO pode renderizar como se estivesse tudo bem.
  // ---------------------------------------------------------------------------
  function validarRegistros(registros) {
    var erros = [];
    if (!Array.isArray(registros)) return ["REGISTROS não é uma lista — os arquivos de registro carregaram?"];
    var vistos = {};
    registros.forEach(function (r, i) {
      var nome = (r && r.arquivo) ? r.arquivo : ("registro na posição " + i);
      OBRIGATORIOS.forEach(function (campo) {
        if (!r || typeof r[campo] !== "string" || r[campo].trim() === "") {
          erros.push(nome + ": campo obrigatório ausente ou vazio: " + campo);
        }
      });
      if (!r) return;
      if (r.tipo && TIPOS.indexOf(r.tipo) === -1) erros.push(nome + ": tipo desconhecido '" + r.tipo + "'");
      if (r.gravidade && GRAVIDADES.indexOf(r.gravidade) === -1) erros.push(nome + ": gravidade desconhecida '" + r.gravidade + "'");
      if (r.autoridade && AUTORIDADES.indexOf(r.autoridade) === -1) erros.push(nome + ": autoridade desconhecida '" + r.autoridade + "'");
      if (r.quando && !ehDataValida(r.quando)) erros.push(nome + ": 'quando' não é data válida: " + r.quando);
      if (r.verificado_em != null && !ehDataValida(r.verificado_em)) erros.push(nome + ": 'verificado_em' não é data válida");
      if (r.tipo === "frente" && FRENTES.indexOf(r.frente) === -1) erros.push(nome + ": tipo 'frente' exige frente entre: " + FRENTES.join(", "));
      if (r.arquivo) {
        if (vistos[r.arquivo]) erros.push(nome + ": arquivo duplicado (dois registros com o mesmo nome)");
        vistos[r.arquivo] = true;
      }
      // Verde é CONQUISTADO, nunca escrito: sem evidência conferida, não há verde.
      if (r.gravidade === "verde" && (!r.evidencia || !r.verificado_em)) {
        erros.push(nome + ": gravidade 'verde' exige evidencia E verificado_em — verde sem prova conferida não existe");
      }
      // Texto é texto: a página insere via textContent; HTML aqui é sempre engano.
      ["titulo", "detalhe"].forEach(function (campo) {
        if (typeof r[campo] === "string" && r[campo].indexOf("<") !== -1) {
          erros.push(nome + ": '" + campo + "' contém '<' — os campos são texto puro, sem HTML");
        }
      });
    });
    // responde_a precisa apontar para registro que exista.
    registros.forEach(function (r) {
      if (r && r.responde_a && !vistos[r.responde_a]) {
        erros.push((r.arquivo || "?") + ": responde_a aponta para registro inexistente: " + r.responde_a);
      }
    });
    return erros;
  }

  function respondidos(registros) {
    var resp = {};
    registros.forEach(function (r) { if (r.responde_a) resp[r.responde_a] = r; });
    return resp;
  }

  // ---------------------------------------------------------------------------
  // A caixa de entrada CALCULADA — o antídoto do H18/H21: pendência é pedido
  // sem resposta. "Uma lista mantida esquece; uma lista calculada não consegue
  // esquecer." Ordenada da mais velha para a mais nova (pedido velho grita mais).
  // ---------------------------------------------------------------------------
  function caixaDeEntrada(registros, agora) {
    var resp = respondidos(registros);
    return registros
      .filter(function (r) { return r.precisa_do_dono === true && !resp[r.arquivo]; })
      .map(function (r) {
        return { registro: r, aguardandoDias: diasEntre(r.quando, agora) };
      })
      .sort(function (a, b) { return b.aguardandoDias - a.aguardandoDias; });
  }

  // Problemas abertos: vermelho/âmbar sem registro que os responda.
  function problemasAbertos(registros) {
    var resp = respondidos(registros);
    return registros.filter(function (r) {
      return (r.gravidade === "vermelho" || r.gravidade === "ambar") &&
        !resp[r.arquivo] && r.tipo !== "pendencia"; // pendência já mora na caixa
    }).sort(function (a, b) { return a.gravidade === "vermelho" ? -1 : 1; });
  }

  // "O que mudou": registros dos últimos N dias, mais recentes primeiro.
  function mudancasRecentes(registros, agora, dias) {
    dias = dias || 7;
    return registros
      .filter(function (r) { return diasEntre(r.quando, agora) <= dias && diasEntre(r.quando, agora) >= 0; })
      .sort(function (a, b) { return paraData(b.quando) - paraData(a.quando); });
  }

  // Estado por frente = o registro MAIS RECENTE daquela frente. Nada é "mantido".
  function estadoDasFrentes(registros) {
    var porFrente = {};
    registros.filter(function (r) { return r.tipo === "frente"; }).forEach(function (r) {
      var atual = porFrente[r.frente];
      if (!atual || paraData(r.quando) > paraData(atual.quando)) porFrente[r.frente] = r;
    });
    return FRENTES.map(function (f) { return { frente: f, registro: porFrente[f] || null }; });
  }

  // ---------------------------------------------------------------------------
  // Frescor COMPUTADO (nunca escrito): para cada registro com vence_em_dias,
  // compara com o agora. E o frescor do livro inteiro: o registro mais recente
  // de todos — se o livro está parado há muito, a capa inteira se denuncia.
  // ---------------------------------------------------------------------------
  function frescor(registros, agora) {
    var vencidos = registros.filter(function (r) {
      return r.vence_em_dias != null && diasEntre(r.quando, agora) > r.vence_em_dias;
    });
    var maisRecente = null;
    registros.forEach(function (r) {
      if (!maisRecente || paraData(r.quando) > paraData(maisRecente.quando)) maisRecente = r;
    });
    return {
      vencidos: vencidos,
      livroParadoHaDias: maisRecente ? diasEntre(maisRecente.quando, agora) : null
    };
  }

  // Relato sem prova conferida — aparece como "não comprovado", jamais como fato.
  function naoComprovados(registros) {
    return registros.filter(function (r) {
      return (r.tipo === "entrega" || r.tipo === "medicao") && (!r.evidencia || !r.verificado_em);
    });
  }

  // ---------------------------------------------------------------------------
  // A CAPA — calculada por exceção, nunca curada. Devolve os blocos na ordem
  // das perguntas do dono (1 preciso agir? 2 algo quebrou? 3 o que mudou?
  // 4 como estamos?). Se passar do teto: devolve erro — o gerador se RECUSA,
  // em vez de crescer (foi assim que a poda de 24/08 durou dois dias).
  // ---------------------------------------------------------------------------
  function capa(registros, agora) {
    return capaComTeto(registros, agora, TETO_BLOCOS_CAPA);
  }

  // Separada para o teste-guarda poder PROVAR que a recusa dispara (um teto
  // que nunca reprovou é um teto que ninguém sabe se reprova — §1).
  function capaComTeto(registros, agora, teto) {
    var blocos = [];
    var caixa = caixaDeEntrada(registros, agora);
    var problemas = problemasAbertos(registros);
    var mudancas = mudancasRecentes(registros, agora, 7);
    var fresc = frescor(registros, agora);
    var semProva = naoComprovados(registros);

    blocos.push({ id: "caixa", titulo: "Precisa de você", itens: caixa });
    if (problemas.length) blocos.push({ id: "problemas", titulo: "Atenção agora", itens: problemas });
    blocos.push({ id: "mudancas", titulo: "O que mudou (7 dias)", itens: mudancas.slice(0, 8) });
    blocos.push({ id: "frentes", titulo: "As frentes", itens: estadoDasFrentes(registros) });
    if (fresc.vencidos.length || (fresc.livroParadoHaDias != null && fresc.livroParadoHaDias > 3)) {
      blocos.push({ id: "frescor", titulo: "O que está velho", itens: fresc.vencidos, livroParadoHaDias: fresc.livroParadoHaDias });
    }
    if (semProva.length) blocos.push({ id: "nao-comprovado", titulo: "Dito, mas não comprovado", itens: semProva });

    if (blocos.length > teto) {
      return {
        erro: "A capa passou do teto de " + teto + " blocos (" + blocos.length +
          "). A regra de cálculo precisa mudar por PR — a capa NÃO cresce.",
        blocos: null
      };
    }
    return { erro: null, blocos: blocos };
  }

  var LOGICA = {
    TIPOS: TIPOS, GRAVIDADES: GRAVIDADES, AUTORIDADES: AUTORIDADES, FRENTES: FRENTES,
    TETO_BLOCOS_CAPA: TETO_BLOCOS_CAPA,
    validarRegistros: validarRegistros,
    caixaDeEntrada: caixaDeEntrada,
    problemasAbertos: problemasAbertos,
    mudancasRecentes: mudancasRecentes,
    estadoDasFrentes: estadoDasFrentes,
    frescor: frescor,
    naoComprovados: naoComprovados,
    capa: capa,
    _capaComTeto: capaComTeto,
    _diasEntre: diasEntre
  };

  if (typeof module !== "undefined" && module.exports) module.exports = LOGICA;
  else raiz.LOGICA = LOGICA;
})(typeof window !== "undefined" ? window : this);
