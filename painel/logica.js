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

  var TIPOS = ["decisao", "pendencia", "resposta", "entrega", "incidente", "medicao", "frente", "rumo", "nota"];
  var GRAVIDADES = ["vermelho", "ambar", "info", "verde"];
  var AUTORIDADES = ["mantenedor", "github", "sonda", "rito", "sessao"];
  var FRENTES = ["site", "comunidade", "curso", "vender", "fabrica"];
  // A ordem do MAPA é a narrativa do Roadmap (fotografia de 26/08): a fundação
  // primeiro, depois o produto, e vender por último — que é também a ordem em
  // que o mantenedor lê o projeto. A ordem de FRENTES acima é só a do vocabulário.
  var ORDEM_DO_MAPA = ["fabrica", "site", "comunidade", "curso", "vender"];
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
  // Validação — o mesmo contrato do gerar_manifesto.js, imposto dos dois lados.
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
      // A frente virou ETIQUETA de qualquer registro (vista "Meu mapa"): é ela que
      // diz em qual capítulo do mapa o fato aparece. Opcional — mas, se vier,
      // tem de ser uma das cinco, senão o fato cai num capítulo que não existe.
      if (r.frente != null && FRENTES.indexOf(r.frente) === -1) {
        erros.push(nome + ": 'frente' desconhecida '" + r.frente + "' — as cinco são: " + FRENTES.join(", "));
      }
      // 'rumo' = para onde esta frente vai. Sem frente ele não tem capítulo onde
      // morar; e rumo NUNCA é verde, porque verde é prova conferida e ninguém
      // consegue provar o futuro. Plano é plano; entrega é que vira verde.
      if (r.tipo === "rumo") {
        if (FRENTES.indexOf(r.frente) === -1) erros.push(nome + ": tipo 'rumo' exige a frente a que ele aponta");
        if (r.gravidade === "verde") erros.push(nome + ": tipo 'rumo' não pode ser verde — verde é prova conferida, e o futuro não se prova");
      }
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
      // -----------------------------------------------------------------------
      // O TIPO dos campos que MOVEM o registro entre as vistas (auditoria de
      // 26/08/2026). Aqui não é preciosismo de tipo: `precisa_do_dono` é o campo
      // que põe um pedido na caixa "Precisa de você", e a caixa só se compara
      // com `=== true`. Escrito como TEXTO ("true", entre aspas) ou esquecido, o
      // registro passava por válido e o pedido SUMIA da caixa em silêncio — que
      // é exatamente a doença do H18 que este livro existe para curar. Uma lista
      // calculada não pode esquecer; para isso, o campo que a alimenta tem de
      // ser obrigatório e do tipo certo.
      // -----------------------------------------------------------------------
      if (typeof r.precisa_do_dono !== "boolean") {
        erros.push(nome + ": 'precisa_do_dono' precisa ser true ou false SEM aspas (veio: " +
          JSON.stringify(r.precisa_do_dono) + ") — é ele que põe o pedido na caixa 'Precisa de você'");
      }
      if (r.vence_em_dias != null && (typeof r.vence_em_dias !== "number" || !isFinite(r.vence_em_dias))) {
        erros.push(nome + ": 'vence_em_dias' precisa ser um número sem aspas, ou null");
      }
      if (r.evidencia != null && (typeof r.evidencia !== "string" || r.evidencia.trim() === "")) {
        erros.push(nome + ": 'evidencia' precisa ser texto com conteúdo, ou null — evidência vazia não é evidência");
      }
    });
    // responde_a precisa apontar para OUTRO registro, que exista.
    registros.forEach(function (r) {
      if (!r || !r.responde_a) return;
      if (!vistos[r.responde_a]) {
        erros.push((r.arquivo || "?") + ": responde_a aponta para registro inexistente: " + r.responde_a);
      }
      // Um registro que responde a SI MESMO fecha o próprio pedido: ele entra e
      // sai da caixa no mesmo instante, sem ninguém responder nada. A caixa não
      // pode ter uma porta que se fecha por dentro.
      if (r.responde_a === r.arquivo) {
        erros.push((r.arquivo || "?") + ": responde_a aponta para o PRÓPRIO registro — um pedido não se responde sozinho");
      }
    });
    // -------------------------------------------------------------------------
    // NÚMERO REPETIDO NO MESMO DIA — o defeito que só nasce com sessões paralelas.
    //
    // O nome de um registro é AAAAMMDD-NNN-slug, e o LEIA-ME manda escolher "a
    // sequência livre do dia". Duas sessões que escolhem ao mesmo tempo escolhem
    // o MESMO número: as duas leem a pasta, as duas veem que 036 está livre. Não
    // é descuido de ninguém — é corrida, e corrida se resolve com trava.
    //
    // Aconteceu QUATRO vezes em 26/08/2026, entre três sessões. Nada se perdeu
    // (o nome completo continua único, e é ele que `responde_a` usa), mas o
    // número deixou de identificar um registro sozinho: "o 037" passou a ser
    // pergunta, não referência. É o mesmo defeito que o
    // `ci/indice_de_armadilhas.py` já recusa nas armadilhas — aqui só se aplica
    // a mesma cura onde ela ainda não estava.
    //
    // As DUAS colisões abaixo ficam congeladas porque já estão na main. Renomear
    // registro mergeado seria editar registro existente, que é a coisa que este
    // livro proíbe acima de tudo (e quebraria os `responde_a` que apontam para o
    // nome completo). O passado fica como está; a regra vale daqui para a frente
    // — o mesmo desenho do marco zero da dívida do livro.
    // -------------------------------------------------------------------------
    // Guarda o TAMANHO tolerado, não um "pode repetir": os pares herdados são
    // dois, e um TERCEIRO registro em 036 seria colisão nova — reprova. Sem
    // isso, congelar um par abriria aquele número para sempre. (Refinamento
    // apontado por outra sessão em 26/08/2026, que desenhou a mesma trava em
    // paralelo.)
    var COLISOES_HERDADAS = { "20260826-036": 2, "20260826-037": 2 };
    var numeros = {};
    registros.forEach(function (r) {
      if (!r || !r.arquivo) return;
      var m = /^(\d{8})-(\d{3})-/.exec(r.arquivo);
      if (!m) return;
      var chave = m[1] + "-" + m[2];
      if (!numeros[chave]) numeros[chave] = [];
      numeros[chave].push(r.arquivo);
    });
    Object.keys(numeros).sort().forEach(function (chave) {
      if (numeros[chave].length <= (COLISOES_HERDADAS[chave] || 1)) return;
      erros.push(
        "número repetido no mesmo dia: " + chave + " foi usado por " +
        numeros[chave].length + " registros (" + numeros[chave].join(", ") +
        "). Outra sessão provavelmente pegou este número enquanto você escrevia. " +
        "Escolha o próximo número LIVRE, renomeie o arquivo E o campo 'arquivo' " +
        "dentro dele (os dois têm de bater), e rode node painel/gerar_manifesto.js de novo."
      );
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
  // Pendência já mora na caixa; frente já mora no bloco de frentes — repetir
  // qualquer uma aqui seria alarme aceso permanente (fadiga de alarme) E um
  // fato morando em dois blocos, que é a doença que este livro cura.
  // ('rumo' também fica de fora: ele mora no Meu mapa, e um plano ainda não
  // cumprido não é um problema aberto — seria alarme aceso o tempo todo.)
  function problemasAbertos(registros) {
    var resp = respondidos(registros);
    return registros.filter(function (r) {
      return (r.gravidade === "vermelho" || r.gravidade === "ambar") &&
        !resp[r.arquivo] && r.tipo !== "pendencia" && r.tipo !== "frente" && r.tipo !== "rumo";
    }).sort(function (a, b) { return a.gravidade === "vermelho" ? -1 : 1; });
  }

  // "O que mudou": registros dos últimos N dias, mais recentes primeiro.
  // Data no FUTURO também entra (auditoria de 26/08/2026): antes o filtro exigia
  // `>= 0` e um registro datado à frente do relógio — erro de digitação, ou o bug
  // de fuso que esta casa já teve (células mostrando hora de Chicago) — SUMIA da
  // capa em silêncio. Sumir é o pior destino possível para um fato: ele fica
  // fresco demais para o painel e invisível para o dono. Aparecer com data
  // estranha é feio e honesto; não aparecer é bonito e mentiroso.
  function mudancasRecentes(registros, agora, dias) {
    dias = dias || 7;
    return registros
      .filter(function (r) { return diasEntre(r.quando, agora) <= dias; })
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
  // MEU MAPA — a vista que responde "para onde estamos indo".
  //
  // O veredito das consultorias prometeu preservar a experiência do Roadmap
  // ("Meu mapa") e a obra de 26/08 não a construiu — a auditoria achou a falta
  // e o mantenedor mandou construir. A regra da casa vale aqui inteira: esta
  // vista NÃO guarda nada. Ela é um agrupamento dos mesmos registros por
  // capítulo, e cada capítulo é uma frente.
  //
  // O que o Roadmap tinha e o livro não tinha: o FUTURO. Por isso nasceu o tipo
  // 'rumo' — para onde uma frente vai. Sem ele, um livro de acontecimentos só
  // sabe dizer de onde viemos. Frente sem rumo registrado não inventa nada:
  // aparece como "não sei para onde esta frente vai", que é o 4º estado da casa
  // aplicado ao futuro.
  // ---------------------------------------------------------------------------
  function meuMapa(registros, agora) {
    var resp = respondidos(registros);
    var estados = {};
    estadoDasFrentes(registros).forEach(function (x) { estados[x.frente] = x.registro; });

    return ORDEM_DO_MAPA.map(function (f) {
      var daFrente = registros.filter(function (r) { return r.frente === f; });
      var rumos = daFrente
        .filter(function (r) { return r.tipo === "rumo" && !resp[r.arquivo]; })
        .sort(function (a, b) { return paraData(b.quando) - paraData(a.quando); });
      var esperando = daFrente
        .filter(function (r) { return r.precisa_do_dono === true && !resp[r.arquivo]; })
        .map(function (r) { return { registro: r, aguardandoDias: diasEntre(r.quando, agora) }; })
        .sort(function (a, b) { return b.aguardandoDias - a.aguardandoDias; });
      var andou = daFrente
        .filter(function (r) { return ["entrega", "decisao", "incidente", "medicao"].indexOf(r.tipo) !== -1; })
        .sort(function (a, b) { return paraData(b.quando) - paraData(a.quando); });
      return {
        frente: f,
        estado: estados[f] || null,   // null = frente sem registro: "não sei"
        rumos: rumos,
        esperando: esperando,
        andou: andou.slice(0, 4)
      };
    });
  }

  // A frase de abertura do mapa — contada, nunca escrita. É o "onde estamos, em
  // uma frase" do Roadmap antigo, com a diferença de que ninguém a atualiza.
  function resumoDoMapa(registros, agora) {
    var capitulos = meuMapa(registros, agora);
    return {
      capitulos: capitulos.length,
      comProvaConferida: capitulos.filter(function (c) { return c.estado && c.estado.gravidade === "verde"; }).length,
      semRegistro: capitulos.filter(function (c) { return !c.estado; }).length,
      semRumo: capitulos.filter(function (c) { return c.rumos.length === 0; }).length,
      esperandoVoce: capitulos.reduce(function (n, c) { return n + c.esperando.length; }, 0)
    };
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
    ORDEM_DO_MAPA: ORDEM_DO_MAPA,
    TETO_BLOCOS_CAPA: TETO_BLOCOS_CAPA,
    validarRegistros: validarRegistros,
    caixaDeEntrada: caixaDeEntrada,
    problemasAbertos: problemasAbertos,
    mudancasRecentes: mudancasRecentes,
    estadoDasFrentes: estadoDasFrentes,
    meuMapa: meuMapa,
    resumoDoMapa: resumoDoMapa,
    frescor: frescor,
    naoComprovados: naoComprovados,
    capa: capa,
    _capaComTeto: capaComTeto,
    _diasEntre: diasEntre
  };

  if (typeof module !== "undefined" && module.exports) module.exports = LOGICA;
  else raiz.LOGICA = LOGICA;
})(typeof window !== "undefined" ? window : this);
