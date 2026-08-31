// static/funil/avisos.js — ligar o aviso na tela do celular.
//
// **A regra que manda em tudo aqui: o navegador só pergunta UMA VEZ.** Uma
// permissão negada não tem segunda chance: o site nunca mais pode perguntar, e
// a pessoa teria que ir aos ajustes do aparelho para voltar atrás. Por isso a
// caixa do sistema só aparece DEPOIS de um toque no nosso botão, nunca ao abrir
// a página, e o cartaz só existe para quem já entrou (`avisos_no_celular.py`).
//
// A ordem completa, e cada passo depende do anterior:
//
//   1. a pessoa toca em "Ligar os avisos";
//   2. o navegador mostra a caixa de permissão dele;
//   3. permitido, o aparelho gera uma INSCRIÇÃO (um endereço no servidor de
//      push do fabricante e duas chaves que cifram o conteúdo);
//   4. a inscrição vai para o NOSSO servidor, que a repassa à `notificacoes`
//      com o token do par. O navegador nunca fala com a célula direto: o token
//      é segredo de servidor.
//
// No iPhone o passo 2 só existe dentro do app INSTALADO. É por isso que o
// cartaz de instalar veio primeiro, e é por isso que aqui, em iOS fora do app,
// este arquivo fica calado em vez de mostrar um botão que não funcionaria.

(function () {
  "use strict";

  var cartaz = document.getElementById("avisos-no-celular");
  if (!cartaz) {
    return;
  }

  var CHAVE_DO_SILENCIO = "meshcraft:avisos:silencio-ate";
  var DIAS_DE_SILENCIO = 30;

  var chavePublica = cartaz.getAttribute("data-chave") || "";
  var enderecoLigar = cartaz.getAttribute("data-ligar") || "";

  function parte(nome) {
    return cartaz.querySelector('[data-parte="' + nome + '"]');
  }

  function mostrarSo(nome) {
    ["convite", "ligado", "nao-deu", "recusado"].forEach(function (cada) {
      var bloco = parte(cada);
      if (bloco) {
        bloco.hidden = cada !== nome;
      }
    });
    cartaz.hidden = false;
  }

  function silenciar() {
    try {
      window.localStorage.setItem(
        CHAVE_DO_SILENCIO,
        String(Date.now() + DIAS_DE_SILENCIO * 24 * 60 * 60 * 1000)
      );
    } catch (e) {
      // Navegação privativa. O cartaz volta na próxima visita, e é melhor
      // assim do que quebrar a página.
    }
  }

  function estaEmSilencio() {
    try {
      var ate = window.localStorage.getItem(CHAVE_DO_SILENCIO);
      return ate !== null && Date.now() < Number(ate);
    } catch (e) {
      return false;
    }
  }

  // A chave pública vem em base64url e o navegador quer bytes crus.
  function chaveEmBytes(base64url) {
    var base64 = (base64url + "===".slice((base64url.length + 3) % 4))
      .replace(/-/g, "+")
      .replace(/_/g, "/");
    var cru = window.atob(base64);
    var bytes = new Uint8Array(cru.length);
    for (var i = 0; i < cru.length; i++) {
      bytes[i] = cru.charCodeAt(i);
    }
    return bytes;
  }

  function comoJson(inscricao) {
    var dados = inscricao.toJSON();
    return {
      endpoint: dados.endpoint,
      p256dh: dados.keys.p256dh,
      auth: dados.keys.auth,
    };
  }

  var ua = navigator.userAgent || "";
  var ehIOS =
    /iPhone|iPad|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function instalado() {
    try {
      if (window.matchMedia("(display-mode: standalone)").matches) {
        return true;
      }
    } catch (e) {
      // matchMedia sem suporte: sobra o sinal do Safari antigo, abaixo.
    }
    return navigator.standalone === true;
  }

  // O cartaz não tem o que fazer sem estas três coisas, e nenhuma delas é
  // culpa da pessoa: navegador antigo, chave não configurada no servidor, ou
  // um iPhone com o site ainda fora da tela de início.
  if (
    !("serviceWorker" in navigator) ||
    !("PushManager" in window) ||
    typeof Notification === "undefined" ||
    !chavePublica ||
    !enderecoLigar ||
    (ehIOS && !instalado())
  ) {
    return;
  }

  // Permissão já negada: o navegador não deixa perguntar de novo, e insistir
  // com um botão que abre nada seria pior que ficar calado. Quem quiser voltar
  // atrás faz isso nos ajustes do aparelho — o cartaz diz isso, e só depois de
  // a pessoa ter tentado nesta visita.
  if (Notification.permission === "denied") {
    return;
  }

  // ---------------------------------------------------------------------
  // QUEM PODE ABRIR A CAIXA DO NAVEGADOR SEM UM TOQUE ANTES
  // ---------------------------------------------------------------------
  // Decisão do mantenedor em 31/08/2026, com as palavras dele: "quero o aviso
  // que aparece no navegador ou na tela, e não um botão na página". Onde o
  // navegador deixa, o pedido abre sozinho e o cartaz nem aparece.
  //
  // **Onde ele NÃO deixa, isto não é preferência nossa e não tem contorno:**
  // a Apple e a Mozilla exigem que `requestPermission()` seja chamado de
  // dentro de um gesto da pessoa. Chamado sozinho ali, ele não abre caixa
  // nenhuma e a promessa volta "default" — o aluno de iPhone ficaria sem
  // aviso para sempre, sem nunca ter visto uma pergunta. Por isso o cartaz
  // continua existindo para eles: é o gesto que a regra exige.
  function abreSozinho() {
    if (ehIOS) {
      return false;
    }
    return !/Firefox|FxiOS/.test(ua);
  }

  function inscrever(registro) {
    return registro.pushManager
      .subscribe({
        // Obrigatório, e é uma promessa: todo push que chegar vai virar um
        // aviso visível. Sem isto o navegador recusa a inscrição.
        userVisibleOnly: true,
        applicationServerKey: chaveEmBytes(chavePublica),
      })
      .then(function (inscricao) {
        return fetch(enderecoLigar, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(comoJson(inscricao)),
        }).then(function (resposta) {
          if (resposta.ok) {
            return "ligado";
          }
          // O servidor não confirmou. Desfazemos a inscrição no aparelho:
          // deixá-la de pé faria o navegador achar que está tudo certo, e a
          // pessoa esperaria um aviso que nunca viria.
          return inscricao.unsubscribe().then(function () {
            return "nao-deu";
          });
        });
      });
  }

  function pedirPermissao(registro) {
    return Notification.requestPermission()
      .then(function (resposta) {
        if (resposta === "granted") {
          return inscrever(registro);
        }
        if (resposta === "denied") {
          // Silenciar aqui é honestidade, não desistência: o navegador não
          // deixaria perguntar de novo de qualquer forma.
          silenciar();
          return "recusado";
        }
        // "default" — a pessoa fechou a caixa sem escolher, OU o navegador
        // engoliu o pedido. O Chrome faz isso quando um site pede permissão
        // sem contexto: em vez da caixa, mostra um ícone quase invisível na
        // barra. Nos dois casos ninguém decidiu nada, e é aqui que o cartaz
        // vira o plano B — ele explica o porquê antes de pedir de novo.
        return "default";
      })
      .catch(function () {
        return "nao-deu";
      });
  }

  navigator.serviceWorker.ready
    .then(function (registro) {
      return registro.pushManager.getSubscription().then(function (jaInscrito) {
        if (jaInscrito) {
          // Este aparelho já recebe avisos. Nada a pedir, nada a mostrar.
          return;
        }
        if (estaEmSilencio()) {
          return;
        }

        var botao = cartaz.querySelector('[data-acao="ligar-avisos"]');
        var depois = cartaz.querySelector('[data-acao="avisos-depois"]');

        if (depois) {
          depois.addEventListener("click", function () {
            silenciar();
            cartaz.hidden = true;
          });
        }

        if (botao) {
          botao.addEventListener("click", function () {
            botao.disabled = true;
            pedirPermissao(registro)
              .then(function (desfecho) {
                mostrarSo(desfecho === "default" ? "convite" : desfecho);
              })
              .then(function () {
                botao.disabled = false;
              });
          });
        }

        if (!abreSozinho()) {
          mostrarSo("convite");
          return;
        }

        // O caminho que o mantenedor pediu: a caixa do navegador, direto.
        // O cartaz só entra em cena quando tem algo a dizer.
        return pedirPermissao(registro).then(function (desfecho) {
          if (desfecho === "ligado") {
            // Deu certo sozinho: a página fica LIMPA. A própria caixa do
            // navegador já foi o aviso, e um cartaz de "pronto" depois dela
            // seria o botão na página que este caminho existe para não ter.
            return;
          }
          // Recusou, deu erro, ou o navegador engoliu o pedido: aí sim o
          // cartaz aparece, porque tem uma explicação a dar.
          mostrarSo(desfecho === "default" ? "convite" : desfecho);
        });
      });
    })
    .catch(function () {
      // Sem service worker pronto não há push nenhum. O site segue igual: o
      // aviso continua na caixa e no sininho, que é a verdade durável.
    });
})();
