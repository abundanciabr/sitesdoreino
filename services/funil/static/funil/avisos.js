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
        mostrarSo("convite");

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
            Notification.requestPermission()
              .then(function (resposta) {
                if (resposta !== "granted") {
                  // Recusou: o cartaz explica o caminho dos ajustes e não
                  // volta a perguntar. Silenciar aqui é honestidade, não
                  // desistência — o navegador não deixaria perguntar de novo
                  // de qualquer forma.
                  silenciar();
                  mostrarSo("recusado");
                  return null;
                }
                return registro.pushManager
                  .subscribe({
                    // Obrigatório, e é uma promessa: todo push que chegar vai
                    // virar um aviso visível. Sem isto o navegador recusa a
                    // inscrição.
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
                        mostrarSo("ligado");
                        return;
                      }
                      // O servidor não confirmou. Desfazemos a inscrição no
                      // aparelho: deixá-la de pé faria o navegador achar que
                      // está tudo certo, e o cartaz nunca mais apareceria
                      // para uma pessoa que na verdade não vai receber nada.
                      return inscricao.unsubscribe().then(function () {
                        mostrarSo("nao-deu");
                      });
                    });
                  });
              })
              .catch(function () {
                mostrarSo("nao-deu");
              })
              .then(function () {
                botao.disabled = false;
              });
          });
        }
      });
    })
    .catch(function () {
      // Sem service worker pronto não há push nenhum. O site segue igual: o
      // aviso continua na caixa e no sininho, que é a verdade durável.
    });
})();
