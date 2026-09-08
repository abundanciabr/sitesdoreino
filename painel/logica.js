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

  // `compromisso` (03/09/2026, degrau 2 do painel de gestão): o que alguém
  // promete fazer nesta semana. Vence em N dias; quem o cumpre escreve um
  // registro que `responde_a` ele. O veredito (cumprido, não cumprido, em
  // aberto) é CALCULADO, nunca marcado à mão — é a cadência de
  // responsabilidade das 4 Disciplinas, sem tabela e sem estado.
  var TIPOS = ["decisao", "pendencia", "resposta", "entrega", "incidente", "medicao", "frente", "rumo", "nota", "compromisso"];
  var FORMATO_DA_FOTO = /^[a-z0-9-]+=-?\d+(\.\d+)?(; [a-z0-9-]+=-?\d+(\.\d+)?)*$/;
  var GRAVIDADES = ["vermelho", "ambar", "info", "verde"];
  var AUTORIDADES = ["mantenedor", "github", "sonda", "rito", "sessao"];
  var FRENTES = ["site", "comunidade", "curso", "vender", "fabrica"];
  // O peso de uma decisão, em três degraus e não em texto livre: vocabulário
  // fechado é o que permite a tela ordenar e colorir sem adivinhar, e o que
  // impede "médio-alto" e "bem grande" de virarem categorias novas em silêncio.
  var IMPACTOS = ["alto", "medio", "baixo"];
  // O LABORATÓRIO (degrau 12): os quatro campos que descrevem uma aposta, e os
  // três desfechos que a fecham. Vocabulário fechado pelo mesmo motivo de
  // `IMPACTOS`: é ele que permite a tela agrupar sem adivinhar, e é ele que
  // impede "meio que deu certo" de virar uma categoria nova em silêncio.
  var CAMPOS_DO_EXPERIMENTO = ["problema", "hipotese", "metrica", "guarda"];
  var VEREDITOS = ["venceu", "perdeu", "nao-deu-para-saber"];
  // OS PORTÕES (degrau 13): os oito que uma escola atravessa antes de escalar.
  // A fase (achando, provando, escalando) é calculada da contagem dos provados,
  // nunca digitada, e por isso o nome de cada um é vocabulário fechado.
  var PORTOES = ["demanda", "conversao", "economia", "entrega", "resultado",
    "retencao", "repeticao", "escala"];
  var FORMATO_DA_METRICA = /^[a-z0-9-]+$/;
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
  // `areas` (07/09/2026, a aba Prioridades) é a lista de painel/areas.json: é ela
  // que diz se o campo `area` de um registro existe. Sem ela, `area` preenchida
  // vira ERRO em vez de passar — não conferir não é aprovar, e um nome inventado
  // poria o fato na parte errada do site.
  function validarRegistros(registros, areas) {
    var erros = [];
    if (!Array.isArray(registros)) return ["REGISTROS não é uma lista — os arquivos de registro carregaram?"];
    var celulasConhecidas = areas ? mapaDeCelulas(areas) : null;
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
      // A ÁREA é o nome do ramo em que o robô trabalhou (`agent/<area>/...`): em
      // que parte do SITE o fato mexe, pergunta que a frente não responde.
      // Opcional (registro antigo não a tem e não se edita); se vier, tem de
      // estar em painel/areas.json, senão o fato cai numa área que não existe.
      if (r.area != null) {
        if (typeof r.area !== "string" || r.area.trim() === "") {
          erros.push(nome + ": 'area' precisa ser o nome do ramo (texto), ou null");
        } else if (!celulasConhecidas) {
          erros.push(nome + ": não consigo conferir a área '" + r.area + "' sem painel/areas.json — quem valida precisa passar as áreas");
        } else if (!celulasConhecidas[r.area]) {
          erros.push(nome + ": 'area' desconhecida '" + r.area + "' — o nome tem de estar em painel/areas.json (é o nome do ramo, como em agent/" + r.area + "/...)");
        }
      }
      // 'rumo' = para onde esta frente vai. Sem frente ele não tem capítulo onde
      // morar; e rumo NUNCA é verde, porque verde é prova conferida e ninguém
      // consegue provar o futuro. Plano é plano; entrega é que vira verde.
      if (r.tipo === "rumo") {
        if (FRENTES.indexOf(r.frente) === -1) erros.push(nome + ": tipo 'rumo' exige a frente a que ele aponta");
        if (r.gravidade === "verde") erros.push(nome + ": tipo 'rumo' não pode ser verde — verde é prova conferida, e o futuro não se prova");
      }
      // Compromisso sem prazo não vence nunca, e um compromisso que não vence
      // não consegue ser "não cumprido": seria promessa sem cobrança.
      if (r.tipo === "compromisso" && !(typeof r.vence_em_dias === "number" && r.vence_em_dias > 0)) {
        erros.push(nome + ": tipo 'compromisso' exige vence_em_dias (número de dias, maior que zero)");
      }
      // A foto da semana (04/09/2026, degrau 6 do painel de gestão): uma
      // `medicao` com o campo `foto`, "cartao=valor; cartao=valor", que o placar
      // lê para dizer o que mudou. Só medição tira foto, e a linha tem forma
      // fixa, senão o placar leria lixo como número.
      if (r.foto !== undefined && r.foto !== null) {
        if (r.tipo !== "medicao") erros.push(nome + ": 'foto' só cabe em registro tipo 'medicao'");
        if (typeof r.foto !== "string" || !FORMATO_DA_FOTO.test(r.foto)) {
          erros.push(nome + ": 'foto' tem a forma \"cartao=valor; cartao=valor\" (nome do cartão em minúsculas e hífens, valor numérico)");
        }
      }
      // -----------------------------------------------------------------------
      // O LABORATÓRIO (05/09/2026, degrau 12 do painel de gestão).
      //
      // Um EXPERIMENTO é uma `medicao` que declara a aposta antes de saber o
      // resultado: o problema que dói, a hipótese, qual número ela quer mover,
      // o que a faz parar antes da hora, e até quando (`vence_em_dias`, o mesmo
      // campo do compromisso — prazo é prazo, e um conceito novo aqui só teria
      // o mesmo comportamento com outro nome).
      //
      // POR QUE OS CINCO ANDAM JUNTOS, e a validação recusa meia declaração:
      // um experimento existe para ser JULGADO depois. Hipótese sem métrica não
      // tem como vencer nem perder; métrica sem prazo nunca é cobrada; qualquer
      // um dos cinco faltando produz, semanas depois, um registro que ninguém
      // consegue fechar — e um laboratório cheio de apostas não julgáveis é
      // pior do que um laboratório vazio, porque parece trabalho.
      //
      // O RESULTADO é outro registro (`responde_a` apontando para o
      // experimento) com `veredito`. Nunca a edição do experimento: registro
      // não se edita nesta casa, e é justamente por isso que a aposta escrita
      // ANTES vale alguma coisa.
      // -----------------------------------------------------------------------
      var declarados = CAMPOS_DO_EXPERIMENTO.filter(function (campo) {
        return r[campo] !== undefined && r[campo] !== null;
      });
      declarados.forEach(function (campo) {
        if (typeof r[campo] !== "string" || r[campo].trim() === "") {
          erros.push(nome + ": '" + campo + "' precisa ser texto com conteúdo, ou null");
        }
        if (r.tipo !== "medicao") {
          erros.push(nome + ": '" + campo + "' só cabe em registro tipo 'medicao' — um experimento é uma medição da casa");
        }
      });
      if (declarados.length) {
        var faltando = CAMPOS_DO_EXPERIMENTO.filter(function (campo) {
          return declarados.indexOf(campo) === -1;
        });
        if (faltando.length) {
          erros.push(nome + ": experimento pela metade — falta " + faltando.join(", ") +
            ". Os quatro andam juntos (problema, hipotese, metrica, guarda), senão " +
            "ninguém consegue julgar esta aposta depois");
        }
        if (!(typeof r.vence_em_dias === "number" && r.vence_em_dias > 0)) {
          erros.push(nome + ": experimento exige vence_em_dias (número de dias, maior que zero) — " +
            "aposta sem prazo nunca vence, e o que não vence nunca é cobrado");
        }
        if (typeof r.metrica === "string" && !FORMATO_DA_METRICA.test(r.metrica)) {
          erros.push(nome + ": 'metrica' é o NOME de um cartão de painel/cartoes/ " +
            "(minúsculas, números e hífens), e não a frase do número");
        }
      }
      // O veredito mora no registro da RESPOSTA, e só faz sentido apontando
      // para o experimento que ele fecha. Solto, ele seria um julgamento sem
      // aposta — e "não deu para saber" é desfecho de primeira classe, com nome
      // próprio, porque metade do valor de um laboratório é poder dizer isso.
      if (r.veredito !== undefined && r.veredito !== null) {
        if (VEREDITOS.indexOf(r.veredito) === -1) {
          erros.push(nome + ": 'veredito' desconhecido '" + r.veredito + "' — os três são: " + VEREDITOS.join(", "));
        }
        if (r.tipo !== "medicao") erros.push(nome + ": 'veredito' só cabe em registro tipo 'medicao'");
        if (!r.responde_a) {
          erros.push(nome + ": 'veredito' sem 'responde_a' não fecha experimento nenhum — " +
            "o resultado é um registro NOVO que aponta para o experimento");
        }
      }
      // O PORTÃO da fase da escola (degrau 13). A fase é CALCULADA dos portões
      // provados, e por isso o nome do portão não pode ser texto livre: um
      // "converssão" escrito com dois esses não contaria para fase nenhuma e
      // ninguém saberia. Vocabulário fechado aqui, na escrita, pelo mesmo
      // desenho de `veredito`: o livro é JavaScript, a tela é Python, e um dos
      // dois lados impõe as palavras.
      if (r.portao !== undefined && r.portao !== null) {
        if (PORTOES.indexOf(r.portao) === -1) {
          erros.push(nome + ": 'portao' desconhecido '" + r.portao + "' — os oito são: " + PORTOES.join(", "));
        }
        // Declarar não é provar. Mesma lei do verde, logo abaixo, e pelo mesmo
        // motivo: portão sem prova conferida promoveria a escola de fase por
        // opinião de quem escreveu o registro.
        if (!r.evidencia || !r.verificado_em) {
          erros.push(nome + ": 'portao' exige evidencia E verificado_em — " +
            "portão sem prova conferida não muda a fase da escola");
        }
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
      // ---------------------------------------------------------------------
      // OS CAMPOS DA DECISÃO — o que um pedido precisa dizer para ser decidível.
      //
      // Achado do GPT e da Fable, na consultoria de 27/08/2026: com cinco
      // frentes e sete merges num dia, o sistema produz decisões mais rápido do
      // que o dono consegue consumi-las — e aí o gargalo passa a ser ELE. A cura
      // não é reduzir o ritmo: é fazer cada pedido chegar decidível, em vez de
      // chegar como uma pergunta que exige reconstruir o contexto inteiro.
      //
      // Os quatro são OPCIONAIS de propósito. Torná-los obrigatórios reprovaria
      // todo pedido antigo e obrigaria a reescrever o passado — que é a única
      // coisa que este livro proíbe acima de tudo. Quem não os traz aparece na
      // tela dizendo "não sei", que é honesto e visível.
      //
      // Mas quando vierem, vêm CERTOS: `reversivel` escrito como texto ("true")
      // passaria por verdadeiro em JavaScript e mentiria na cara do dono sobre
      // a coisa que mais importa numa decisão — se dá para voltar atrás. É a
      // mesma família do `precisa_do_dono` escrito com aspas, que fazia um
      // pedido sumir da caixa em silêncio (auditoria de 26/08/2026).
      // ---------------------------------------------------------------------
      if (r.se_eu_nao_decidir != null && (typeof r.se_eu_nao_decidir !== "string" || r.se_eu_nao_decidir.trim() === "")) {
        erros.push(nome + ": 'se_eu_nao_decidir' precisa ser texto com conteúdo, ou null");
      }
      if (r.recomendacao != null && (typeof r.recomendacao !== "string" || r.recomendacao.trim() === "")) {
        erros.push(nome + ": 'recomendacao' precisa ser texto com conteúdo, ou null");
      }
      if (r.reversivel != null && typeof r.reversivel !== "boolean") {
        erros.push(nome + ": 'reversivel' precisa ser true ou false SEM aspas (veio: " +
          JSON.stringify(r.reversivel) + ") — texto entre aspas passaria por verdadeiro e mentiria " +
          "sobre a única coisa que decide se um erro custa caro");
      }
      if (r.impacto != null && IMPACTOS.indexOf(r.impacto) === -1) {
        erros.push(nome + ": 'impacto' desconhecido '" + r.impacto + "' — os três são: " + IMPACTOS.join(", "));
      }
      // Um pedido que descreve o custo de não decidir e NÃO é para o dono é
      // contradição: ou o texto está no registro errado, ou o `precisa_do_dono`
      // ficou false por engano — e um pedido com false não entra na caixa.
      if (r.precisa_do_dono !== true && (r.se_eu_nao_decidir != null || r.recomendacao != null)) {
        erros.push(nome + ": tem campo de decisão ('se_eu_nao_decidir'/'recomendacao') " +
          "mas 'precisa_do_dono' é false — ele nunca apareceria na caixa, e o texto se perderia");
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

  // O mapa "quem já foi respondido". `prontos` existe porque a página passou a
  // abrir com um RESUMO (um subconjunto do livro) em vez do livro inteiro: um
  // pedido cuja RESPOSTA ficou fora do subconjunto pareceria eternamente aberto,
  // e a caixa "Precisa de você" voltaria a mentir — a doença do H18, por dentro
  // da própria cura. O gerador calcula este mapa sobre o livro INTEIRO e o
  // embute no resumo; quem tem o livro todo em mãos não passa nada e o cálculo
  // é o de sempre. Uma função só, dois chamadores, zero divergência.
  function respondidos(registros, prontos) {
    if (prontos) return prontos;
    var resp = {};
    registros.forEach(function (r) { if (r.responde_a) resp[r.responde_a] = r; });
    return resp;
  }

  // ---------------------------------------------------------------------------
  // A caixa de entrada CALCULADA — o antídoto do H18/H21: pendência é pedido
  // sem resposta. "Uma lista mantida esquece; uma lista calculada não consegue
  // esquecer." Ordenada da mais velha para a mais nova (pedido velho grita mais).
  // ---------------------------------------------------------------------------
  function caixaDeEntrada(registros, agora, prontos) {
    var resp = respondidos(registros, prontos);
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
  function problemasAbertos(registros, prontos) {
    var resp = respondidos(registros, prontos);
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
  function meuMapa(registros, agora, prontos) {
    var resp = respondidos(registros, prontos);
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
  function resumoDoMapa(registros, agora, prontos) {
    var capitulos = meuMapa(registros, agora, prontos);
    return {
      capitulos: capitulos.length,
      comProvaConferida: capitulos.filter(function (c) { return c.estado && c.estado.gravidade === "verde"; }).length,
      semRegistro: capitulos.filter(function (c) { return !c.estado; }).length,
      semRumo: capitulos.filter(function (c) { return c.rumos.length === 0; }).length,
      esperandoVoce: capitulos.reduce(function (n, c) { return n + c.esperando.length; }, 0)
    };
  }

  // ---------------------------------------------------------------------------
  // PRIORIDADES POR ÁREA (07/09/2026) — "o que eu faço primeiro, e em que parte
  // do site isso mexe". A capa ordena por idade e o Meu mapa agrupa pelos cinco
  // capítulos do livro; nenhuma das duas responde essa pergunta. Aqui os MESMOS
  // fatos são recortados por área do site (painel/areas.json) e, dentro dela,
  // por tipo. As tarefas vêm de fora (a fila dos robôs, buscada pela página)
  // porque não moram no livro; sem elas os grupos de registro continuam de pé.
  // ---------------------------------------------------------------------------

  // Registro sem `area` cai na frente dele. É aproximação, a tela a marca como
  // tal, e existe para os registros escritos antes do campo, que não se editam.
  var AREA_DA_FRENTE = { fabrica: "fabrica", curso: "cursos", site: "alunos", comunidade: "comunidade", vender: "vendas" };
  var RANK_IMPACTO = { alto: 0, medio: 1, baixo: 2 };
  // A MESMA escala do selo da fila (alta ≡ alto), para pedido e tarefa caberem
  // na mesma lista. Os limiares que produzem o selo moram na fila e NÃO se
  // reimplementam aqui: duas definições de "custa caro" divergem sozinhas
  // (`armadilhas/379`).
  var RANK_SELO = { alta: 0, media: 1, baixa: 2, "sem-nota": 3 };
  var SEM_AREA = { id: null, nome: "❓ Sem área reconhecida", diz: "ninguém disse em que parte do site isto mexe" };

  function mapaDeCelulas(areas) {
    var m = {};
    (areas || []).forEach(function (a) {
      if (a && Array.isArray(a.celulas)) a.celulas.forEach(function (c) { m[c] = a.id; });
    });
    return m;
  }

  // Ids únicos, campos presentes, e cada célula em UMA área só: sem isso o mesmo
  // trabalho apareceria em dois blocos, e a contagem do topo não fecharia com a
  // soma deles.
  function validarAreas(areas) {
    var erros = [];
    if (!Array.isArray(areas)) return ["painel/areas.json: 'areas' precisa ser uma lista"];
    if (!areas.length) return ["painel/areas.json: a lista de áreas está vazia"];
    var ids = {}, dona = {};
    areas.forEach(function (a, i) {
      var nome = (a && a.id) ? a.id : ("área na posição " + i);
      ["id", "nome", "diz"].forEach(function (campo) {
        if (!a || typeof a[campo] !== "string" || a[campo].trim() === "") {
          erros.push(nome + ": campo '" + campo + "' ausente ou vazio");
        }
      });
      if (!a) return;
      if (ids[a.id]) erros.push(nome + ": id repetido — duas áreas com o mesmo id");
      ids[a.id] = true;
      if (!Array.isArray(a.celulas) || !a.celulas.length) {
        erros.push(nome + ": 'celulas' precisa ser uma lista com ao menos um nome de célula ou de ramo");
        return;
      }
      a.celulas.forEach(function (c) {
        if (typeof c !== "string" || c.trim() === "") { erros.push(nome + ": nome de célula vazio"); return; }
        if (dona[c]) {
          erros.push("a célula '" + c + "' aparece em duas áreas ('" + dona[c] + "' e '" + a.id +
            "') — cada nome pertence a uma só, senão o mesmo trabalho apareceria em dois lugares da tela");
        } else { dona[c] = a.id; }
      });
    });
    return erros;
  }

  // Compara chaves de ordenação (listas de números e textos), campo a campo.
  function porOrdem(a, b) {
    for (var i = 0; i < Math.max(a.ordem.length, b.ordem.length); i++) {
      var x = a.ordem[i], y = b.ordem[i];
      if (x === y) continue;
      return x < y ? -1 : 1;
    }
    return 0;
  }

  // O roteamento é conservador: Luna só atende uma operação que o próprio
  // texto declara mecânica e limitada por regra. Sem as duas provas, Terra
  // recebe a tarefa cotidiana, pois adivinhar a natureza do trabalho custa
  // mais do que usar o modelo geral.
  function modeloParaTarefa(tarefa) {
    tarefa = tarefa || {};
    var texto = [tarefa.titulo, tarefa.o_que_muda, tarefa.prompt]
      .concat(Array.isArray(tarefa.onde) ? tarefa.onde : [])
      .filter(function (parte) { return typeof parte === "string"; })
      .join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    var eMecanica = /\b(extrac(?:ao|oes)|classificac(?:ao|oes)|formatac(?:ao|oes)|alterac(?:ao|oes) mecanic(?:a|as))\b/.test(texto);
    var regraDeclarada = /\b(regra clara|regra (?:ja )?(?:definida|escrita)|criterio (?:ja )?definido|formato (?:ja )?definido)\b/.test(texto);
    return eMecanica && regraDeclarada
      ? { modelo: "Luna", raciocinio: "Low" }
      : { modelo: "Terra", raciocinio: "Low" };
  }

  function prioridades(registros, agora, prontos, areas, tarefas) {
    areas = areas || [];
    tarefas = tarefas || [];
    var deCelula = mapaDeCelulas(areas);
    var resp = respondidos(registros, prontos);
    var caixa = caixaDeEntrada(registros, agora, prontos);
    var naCaixa = {};
    caixa.forEach(function (x) { naCaixa[x.registro.arquivo] = true; });

    function areaDoRegistro(r) {
      if (r.area && deCelula[r.area]) return { id: deCelula[r.area], pelaFrente: false };
      if (r.frente && AREA_DA_FRENTE[r.frente]) return { id: AREA_DA_FRENTE[r.frente], pelaFrente: true };
      return { id: null, pelaFrente: false };
    }

    var itens = [];
    // DECIDIR: pedidos do livro e tarefas paradas à espera dele, na mesma lista
    // e na mesma escala. No empate, o registro vem antes, e o mais velho antes.
    caixa.forEach(function (x) {
      var r = x.registro, a = areaDoRegistro(r);
      var peso = RANK_IMPACTO[r.impacto] == null ? 3 : RANK_IMPACTO[r.impacto];
      itens.push({
        grupo: "decidir", especie: "pedido", area: a.id, pelaFrente: a.pelaFrente,
        registro: r, dias: x.aguardandoDias, cor: "gold",
        ordem: [peso, 0, -x.aguardandoDias, r.arquivo]
      });
    });
    // ALERTA: vermelho e âmbar sem conserto, MENOS o que já está na caixa. Um
    // fato, um lugar: o pedido que também é âmbar mora só em Decidir.
    problemasAbertos(registros, prontos).forEach(function (r) {
      if (naCaixa[r.arquivo]) return;
      var a = areaDoRegistro(r), d = diasEntre(r.quando, agora);
      itens.push({
        grupo: "alerta", especie: "alerta", area: a.id, pelaFrente: a.pelaFrente,
        registro: r, dias: d, cor: r.gravidade === "vermelho" ? "red" : "gold",
        ordem: [r.gravidade === "vermelho" ? 0 : 1, -d, r.arquivo]
      });
    });
    // RUMOS E PROMESSAS. Compromisso vencido vira bolinha vermelha: o prazo é
    // contado contra o relógio de quem abre a página, nunca congelado no build.
    registros.forEach(function (r) {
      if (r.tipo !== "rumo" && r.tipo !== "compromisso") return;
      if (resp[r.arquivo]) return;
      var a = areaDoRegistro(r), d = diasEntre(r.quando, agora);
      var vence = r.vence_em_dias != null ? (r.vence_em_dias - d) : null;
      itens.push({
        grupo: "rumo", especie: r.tipo, area: a.id, pelaFrente: a.pelaFrente,
        registro: r, dias: d, venceEm: vence,
        cor: (vence != null && vence < 0) ? "red" : "blue",
        ordem: [r.tipo === "compromisso" ? 0 : 1, d, r.arquivo]
      });
    });
    // A FILA DOS ROBÔS: a área e o selo já vêm resolvidos por quem serve a fila.
    tarefas.forEach(function (t) {
      var paraODono = t.para_o_dono === true;
      var classe = (t.selo && t.selo.classe) || "sem-nota";
      var rank = RANK_SELO[classe] == null ? 3 : RANK_SELO[classe];
      var peso = typeof t.importancia === "number" ? t.importancia : 0;
      itens.push({
        grupo: paraODono ? "decidir" : "robos", especie: "tarefa",
        area: t.area || null, pelaFrente: false, tarefa: t,
        cor: paraODono ? "gold" : (t.estado === "na fila" ? "blue" : "roxo"),
        ordem: paraODono ? [rank, 1, 0, t.id] : [rank, -peso, t.id]
      });
    });

    function areaVazia(a) {
      return { id: a.id, nome: a.nome, diz: a.diz, total: 0,
        grupos: { decidir: [], alerta: [], robos: [], rumo: [] } };
    }
    // TODAS as áreas aparecem, mesmo vazias: área que some se leria como "não
    // existe", e não como "nada pendente hoje".
    var saida = areas.map(areaVazia);
    var porId = {};
    saida.forEach(function (a) { porId[a.id] = a; });
    var sem = areaVazia(SEM_AREA);
    itens.forEach(function (i) {
      var destino = porId[i.area] || sem;
      destino.grupos[i.grupo].push(i);
      destino.total++;
    });
    saida.concat([sem]).forEach(function (a) {
      Object.keys(a.grupos).forEach(function (g) { a.grupos[g].sort(porOrdem); });
    });
    return { areas: saida, semArea: sem };
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
  function capa(registros, agora, prontos) {
    return capaComTeto(registros, agora, TETO_BLOCOS_CAPA, prontos);
  }

  // Separada para o teste-guarda poder PROVAR que a recusa dispara (um teto
  // que nunca reprovou é um teto que ninguém sabe se reprova — §1).
  function capaComTeto(registros, agora, teto, prontos) {
    var blocos = [];
    var caixa = caixaDeEntrada(registros, agora, prontos);
    var problemas = problemasAbertos(registros, prontos);
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

  // ---------------------------------------------------------------------------
  // POSSO CONFIAR NISTO? — a quinta pergunta, e a melhor da consultoria inteira.
  //
  // As quatro perguntas da capa olham para o PROJETO (preciso decidir? algo
  // quebrou? o que mudou? como estamos?). O GPT acrescentou uma que olha para o
  // PAINEL, e o veredito das consultorias a chamou de "a melhor da consultoria
  // inteira": *posso confiar no que estou lendo aqui?*
  //
  // Todas as outras vistas medem o projeto. Nenhuma media a confiabilidade da
  // fonte. E o instrumento continua funcionando mesmo se todo o resto do painel
  // estiver mentindo — porque ele conta a própria falta de prova.
  //
  // Estas contas são feitas sobre o livro INTEIRO, no build, e viajam prontas:
  // calculá-las no navegador sobre o resumo daria um número errado com cara de
  // certo, já que o resumo é um recorte. São clock-independentes por
  // construção — presença de evidência não muda com a hora.
  // ---------------------------------------------------------------------------

  // Os tipos que AFIRMAM alguma coisa sobre o mundo, e portanto podem ser
  // cobrados por prova. Uma `nota` ou uma `decisao` não afirmam que algo
  // funciona; uma `entrega` e uma `medicao`, sim.
  var TIPOS_QUE_AFIRMAM = ["entrega", "medicao"];

  function confianca(registros) {
    var afirmacoes = registros.filter(function (r) {
      return TIPOS_QUE_AFIRMAM.indexOf(r.tipo) !== -1;
    });
    var comProva = afirmacoes.filter(function (r) { return r.evidencia && r.verificado_em; });

    // O PLACAR DE CALIBRAÇÃO (joia do Opus, que ele chamou de "a peça que
    // faltava"): todas as 13 ideias da reforma medem o PROJETO; nenhuma media a
    // confiabilidade de quem reporta. Aqui a conta é promessa × entrega — para
    // cada rumo que foi cumprido, quantos dias entre prometer e cumprir.
    //
    // O cuidado que ele mesmo registrou: pontue CALIBRAÇÃO, nunca ambição.
    // Premiar rumo cumprido rápido ensinaria a prometer menos. Por isso o que
    // sai daqui é a contagem e a mediana — nunca uma nota.
    var resp = respondidos(registros);
    var cumpridos = [];
    registros.forEach(function (r) {
      if (r.tipo !== "rumo") return;
      var fecha = resp[r.arquivo];
      if (!fecha) return;
      cumpridos.push({
        rumo: r.arquivo,
        titulo: r.titulo,
        prometido: r.quando,
        cumprido: fecha.quando,
        dias: Math.max(0, diasEntre(r.quando, paraData(fecha.quando)))
      });
    });
    cumpridos.sort(function (a, b) { return a.dias - b.dias; });
    var mediana = cumpridos.length
      ? cumpridos[Math.floor((cumpridos.length - 1) / 2)].dias
      : null;

    var abertos = registros.filter(function (r) {
      return r.tipo === "rumo" && !resp[r.arquivo];
    }).length;

    return {
      afirmacoes: afirmacoes.length,
      comProvaConferida: comProva.length,
      // Nomes, e não só a contagem: "6 de 24 sem prova" manda procurar, e não
      // adianta se não disser QUAIS. Limitado, porque a lista é para agir.
      semProva: afirmacoes.filter(function (r) { return !(r.evidencia && r.verificado_em); })
        .slice(0, 8).map(function (r) { return { arquivo: r.arquivo, titulo: r.titulo }; }),
      rumosCumpridos: cumpridos.length,
      rumosAbertos: abertos,
      medianaDeDias: mediana,
      // O mais devagar e o mais rápido, para o dono ver a DISPERSÃO em vez de
      // uma média que esconde tudo.
      maisRapido: cumpridos.length ? cumpridos[0] : null,
      maisDevagar: cumpridos.length ? cumpridos[cumpridos.length - 1] : null
    };
  }

  // ---------------------------------------------------------------------------
  // O RESUMO — o que a página precisa para desenhar a capa e o mapa, e nada mais.
  //
  // POR QUE ISTO EXISTE: até 27/08/2026 abrir o painel custava o livro INTEIRO —
  // primeiro um pedido por registro (86 numa rajada, o incidente das quatro telas
  // vermelhas), depois um arquivo só de 182 KB que crescia para sempre. Nos dois
  // desenhos o custo de abrir era proporcional a toda a história do projeto, num
  // livro que recebeu 48 registros num único dia.
  //
  // A REGRA DE OURO DESTA FUNÇÃO: ela não tem relógio. Só decide PERTENCIMENTO —
  // quem entra na caixa, quais são os problemas abertos, o que cada capítulo do
  // mapa mostra —, e isso não depende de que horas são. Tudo que depende do
  // relógio (há quantos dias espera, o que venceu, o que mudou nos últimos 7
  // dias) continua sendo contado NO NAVEGADOR, ao abrir, contra o relógio dele.
  // Congelar essas contas no build seria fossilizar o frescor, que é exatamente
  // a doença que o painel existe para não ter (correção 3 do veredito das
  // consultorias, 4 de 5).
  //
  // Por isso ela chama as MESMAS funções da capa e do mapa, com uma data
  // sentinela: o que ela lê do resultado é só quem entrou, nunca quantos dias.
  // Uma regra só, dois momentos de execução, zero divergência.
  // ---------------------------------------------------------------------------

  // Quanto o resumo pode pesar antes de o gerador RECUSAR construir. Não é um
  // número mágico: é ~3x o tamanho medido em 27/08/2026 (52 KB com 95
  // registros). Estourar não é defeito do painel — é sinal de que algo real está
  // se acumulando (pedidos sem resposta, entregas sem prova), e a resposta certa
  // é olhar o acúmulo, não subir o teto. Mesma lei do TETO_BLOCOS_CAPA.
  var ORCAMENTO_RESUMO_BYTES = 150 * 1024;
  var ORCAMENTO_PAINEL_BYTES = 300 * 1024;

  // Quantos registros recentes viajam no resumo. A capa mostra no máximo 8 dos
  // últimos 7 dias, mas quem decide QUAIS 8 é o relógio do navegador — então o
  // resumo carrega uma folga e deixa o corte para lá.
  var RECENTES_NO_RESUMO = 30;
  // Destes, os que viajam com o texto completo (a capa os desenha abertos).
  var RECENTES_COM_DETALHE = 10;

  // O MESMO teto para "Atenção agora", e ele nasceu de uma medição, em
  // 02/09/2026: o resumo tinha **11 bytes** de folga no orçamento de 150 KB, e o
  // próximo registro de qualquer robô ia reprovar a muralha do painel. Como a lei
  // manda todo PR trazer o seu registro, isso travaria o repositório inteiro.
  //
  // O QUE estava se acumulando (a pergunta que o gerador manda fazer antes de
  // pensar no teto): "Atenção agora" é calculado como *vermelho ou âmbar sem
  // resposta*, e um incidente quase nunca ganha registro de resposta — ele é
  // consertado, o conserto vira uma ENTREGA, e o incidente fica aberto para
  // sempre. Medido no mesmo dia: 49 KB do resumo eram incidentes, um deles de
  // 4,5 KB, vários de cinco dias antes. Um bloco que só cresce dentro de um
  // orçamento que não cresce tem data marcada, e a data chegou.
  //
  // O CORTE É DE TEXTO, NUNCA DE FATO. Todos os problemas abertos continuam
  // listados, contados no cabeçalho do bloco e clicáveis; os mais antigos vão
  // como título, com a linha que diz onde o texto está (`soTitulo`). Sumir com
  // um problema seria a doença que este painel existe para curar; mostrar
  // vinte parágrafos de agosto na tela de hoje é outra forma da mesma doença.
  var PROBLEMAS_COM_DETALHE = 10;

  // O MESMO teto para a caixa "Precisa de você" — e ele nasceu da MESMA medição,
  // dois dias depois (TAR-119, 04/09/2026): o resumo estava em 137,1 KB dos
  // 150 KB do orçamento (91,4%), e a caixa era a ÚNICA fonte de texto completo
  // sem teto nenhum. Dez pedidos abertos pesavam 22,4 KB, e cada pedido novo
  // custava um parágrafo inteiro dentro de um orçamento que não cresce.
  //
  // POR QUE a caixa cresce e não encolhe sozinha: quem a esvazia é o dono,
  // respondendo — e cinco frentes produzem decisões mais depressa do que uma
  // pessoa as consome. Um bloco que só ele pode encolher, dentro de um
  // orçamento fixo, tem data marcada. É a frase que se escreveu aqui em 02/09
  // sobre os incidentes, e ela valia igual para a caixa.
  //
  // O CORTE É DE TEXTO, NUNCA DE FATO, e aqui isso tem nome próprio: os quatro
  // campos da decisão (`se_eu_nao_decidir`, `recomendacao`, `reversivel`,
  // `impacto`) já viajam em `CAMPOS_DO_TITULO`, então o pedido cortado continua
  // DECIDÍVEL — perde o parágrafo, não a decisão, e a ficha que a página desenha
  // embaixo dele continua cheia. Os dez pedidos abertos em 04/09 foram medidos
  // um a um antes deste corte: todos com os quatro campos.
  //
  // QUEM FICA COM O TEXTO SÃO OS MAIS RECENTES, e não os do topo do bloco: a
  // caixa é ordenada do mais velho para o mais novo ("pedido velho grita mais"),
  // e um pedido que está na capa há dias já foi lido. O que o dono ainda não viu
  // é o de hoje.
  //
  // E é uma CONTAGEM, não uma idade. "Pendência com mais de N dias" seria mais
  // bonito de ler e cruzaria a linha que este arquivo não cruza: congelaria o
  // relógio do build dentro do resumo. A ordem por data dá o mesmo resultado com
  // qualquer relógio; a idade, não.
  var CAIXA_COM_DETALHE = 4;

  // Os campos que sobrevivem quando um registro viaja só como título. O `detalhe`
  // fica de fora de propósito: nos blocos recolhidos a página NUNCA o mostra
  // (`.item.recolhido .det{display:none}`, e não há nenhum clique que o abra) —
  // até hoje ele viajava para dentro do DOM para nunca ser lido. Quem quiser o
  // texto inteiro abre a Memória, e aí o mês carrega.
  var CAMPOS_DO_TITULO = ["arquivo", "tipo", "quando", "titulo", "autoridade",
    "evidencia", "verificado_em", "precisa_do_dono", "responde_a", "gravidade",
    "frente", "vence_em_dias",
    // A ÁREA vem no corte: sem ela, o registro que viaja só como título cairia
    // em "sem área reconhecida" na aba Prioridades, e a tela mostraria o fato na
    // parte errada do site tendo a resposta escrita no livro.
    "area",
    // Os campos da decisão vêm mesmo no corte: um pedido da caixa que viajasse
    // sem eles apareceria como "não sei o que acontece" tendo a resposta
    // escrita no livro — pior do que não ter a resposta.
    "se_eu_nao_decidir", "recomendacao", "reversivel", "impacto"];
  // Os campos do EXPERIMENTO ficam de fora desta lista de propósito (05/09/2026,
  // degrau 12). O painel do dono não desenha o laboratório em canto nenhum — a
  // tela dele é `/admin/placar/laboratorio/`, e ela lê os registros de origem,
  // não este resumo. Carregá-los aqui gastaria o orçamento do resumo (que em
  // 04/09/2026 estava a 91% do teto) com texto que nenhuma tela abre.

  function soTitulo(r) {
    var o = {};
    CAMPOS_DO_TITULO.forEach(function (c) { if (r[c] !== undefined) o[c] = r[c]; });
    // `detalhe` é campo OBRIGATÓRIO e não-vazio (a validação acima cobra isso).
    // Em vez de burlar com string vazia, ele carrega a única coisa verdadeira
    // que se pode dizer aqui: onde o texto está. Assim o registro continua
    // válido pelo mesmo contrato, e a página não mostra um branco que se leria
    // como "não havia nada a dizer".
    o.detalhe = "O texto deste registro não veio junto com a página — ele está na aba Memória, no mês " +
      (r.arquivo || "").slice(0, 4) + "-" + (r.arquivo || "").slice(4, 6) + ".";
    o._so_titulo = true;
    return o;
  }

  function montarResumo(registros) {
    // Data sentinela: só o PERTENCIMENTO destes resultados é usado.
    var sentinela = new Date("2000-01-01T12:00:00");
    var prontos = respondidos(registros);
    var capaS = capaComTeto(registros, sentinela, TETO_BLOCOS_CAPA, prontos);
    if (capaS.erro) return { erro: capaS.erro };
    var mapaS = meuMapa(registros, sentinela, prontos);

    var porData = registros.slice().sort(function (a, b) { return paraData(b.quando) - paraData(a.quando); });
    var recentes = porData.slice(0, RECENTES_NO_RESUMO);

    var completo = {}, apenasTitulo = {};
    function marcar(alvo, lista) {
      (lista || []).forEach(function (x) {
        var r = (x && x.registro !== undefined) ? x.registro : x;
        if (r && r.arquivo) alvo[r.arquivo] = true;
      });
    }
    var blocos = {};
    capaS.blocos.forEach(function (b) { blocos[b.id] = b.itens; });

    // COM texto: o que a página desenha aberto.
    // "Precisa de você" com teto de TEXTO (ver `CAIXA_COM_DETALHE`): os pedidos
    // mais RECENTES levam o parágrafo. A ordem do bloco é do mais velho para o
    // mais novo, e usá-la aqui deixaria o texto justamente com os pedidos que o
    // dono já leu na capa nos últimos dias.
    var caixaPorData = (blocos.caixa || []).slice().sort(function (a, b) {
      return paraData(b.registro.quando) - paraData(a.registro.quando);
    });
    marcar(completo, caixaPorData.slice(0, CAIXA_COM_DETALHE));
    // "Atenção agora" com teto de TEXTO (ver `PROBLEMAS_COM_DETALHE`): os mais
    // RECENTES levam o parágrafo, o resto vai como título. A ordem do bloco é
    // por gravidade, e usá-la aqui deixaria o texto com os incidentes mais
    // VELHOS — que é o contrário do que alguém abre a capa para ler.
    var problemasPorData = (blocos.problemas || []).slice().sort(function (a, b) {
      return paraData(b.quando) - paraData(a.quando);
    });
    marcar(completo, problemasPorData.slice(0, PROBLEMAS_COM_DETALHE));
    marcar(completo, recentes.slice(0, RECENTES_COM_DETALHE));
    mapaS.forEach(function (c) {
      if (c.estado) completo[c.estado.arquivo] = true;
      marcar(completo, c.rumos);
    });

    // SÓ título: o que a página desenha recolhido, ou como uma linha.
    // Os problemas abertos entram INTEIROS aqui e a linha final tira os que já
    // estão em `completo`: assim nenhum deles some do resumo, e só o texto dos
    // antigos fica para trás.
    // A caixa inteira entra aqui, e a linha final tira os que já estão em
    // `completo`. Sem esta linha o pedido cortado acima SUMIRIA do resumo: ele
    // só teria outra porta se tivesse `frente`, pelo `esperando` do Meu mapa —
    // e pedido sem frente é comum. Sumir é o pior destino possível para um fato.
    marcar(apenasTitulo, blocos.caixa);
    marcar(apenasTitulo, blocos.problemas);
    marcar(apenasTitulo, blocos.frentes);
    marcar(apenasTitulo, blocos["nao-comprovado"]);
    marcar(apenasTitulo, blocos.frescor);
    marcar(apenasTitulo, recentes);
    marcar(apenasTitulo, registros.filter(function (r) { return r.vence_em_dias != null; }));
    mapaS.forEach(function (c) { marcar(apenasTitulo, c.andou); marcar(apenasTitulo, c.esperando); });
    Object.keys(completo).forEach(function (id) { delete apenasTitulo[id]; });

    var selecionados = registros.filter(function (r) {
      return completo[r.arquivo] || apenasTitulo[r.arquivo];
    }).map(function (r) { return completo[r.arquivo] ? r : soTitulo(r); });

    // O mapa de respostas viaja calculado sobre o livro INTEIRO: sem ele, um
    // pedido cuja resposta ficou fora do resumo voltaria a aparecer como aberto.
    var respondidosIds = {};
    Object.keys(prontos).forEach(function (k) { respondidosIds[k] = true; });

    return {
      erro: null,
      respondidos: respondidosIds,
      // Contado sobre o livro INTEIRO, aqui, e não no navegador: lá só existe o
      // recorte, e "6 de 24" viraria um número errado com cara de certo.
      confianca: confianca(registros),
      registros: selecionados,
      // O registro mais recente do livro TODO — é dele que sai "o livro está
      // parado há N dias", e ele precisa ser o do livro, não o do resumo.
      maisRecenteQuando: porData.length ? porData[0].quando : null,
      totalNoLivro: registros.length
    };
  }

  var LOGICA = {
    TIPOS: TIPOS, GRAVIDADES: GRAVIDADES, AUTORIDADES: AUTORIDADES, FRENTES: FRENTES,
    ORDEM_DO_MAPA: ORDEM_DO_MAPA,
    IMPACTOS: IMPACTOS,
    CAMPOS_DO_EXPERIMENTO: CAMPOS_DO_EXPERIMENTO,
    VEREDITOS: VEREDITOS,
    PORTOES: PORTOES,
    TETO_BLOCOS_CAPA: TETO_BLOCOS_CAPA,
    PROBLEMAS_COM_DETALHE: PROBLEMAS_COM_DETALHE,
    CAIXA_COM_DETALHE: CAIXA_COM_DETALHE,
    ORCAMENTO_RESUMO_BYTES: ORCAMENTO_RESUMO_BYTES,
    ORCAMENTO_PAINEL_BYTES: ORCAMENTO_PAINEL_BYTES,
    montarResumo: montarResumo,
    confianca: confianca,
    validarRegistros: validarRegistros,
    validarAreas: validarAreas,
    modeloParaTarefa: modeloParaTarefa,
    prioridades: prioridades,
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
