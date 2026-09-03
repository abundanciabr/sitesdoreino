// static/funil/avisos.js — ligar o aviso na tela do celular.
//
// **A regra que manda em tudo aqui: o navegador só pergunta UMA VEZ.** Uma
// permissão negada não tem segunda chance: o site nunca mais pode perguntar, e
// a pessoa teria que ir aos ajustes do aparelho para voltar atrás. Por isso a
// caixa do sistema só aparece DEPOIS de um toque no nosso botão, nunca ao abrir
// a página, e o cartaz só existe para quem já entrou (`avisos_no_celular.py`).
//
// **E "nunca ao abrir a página" é lei de sobrevivência, não estilo.** Em
// 31/08/2026 este arquivo abria o pedido sozinho onde o navegador deixava
// (registro 20260831-075), e no MESMO dia o Malwarebytes Browser Guard passou
// a bloquear o meshcraft.top inteiro como site malicioso, por "excesso de
// solicitação de notificações": pedir permissão sem gesto, página após página,
// é a assinatura que as ferramentas de segurança caçam. O cartaz com botão é o
// único caminho que existe, em todo navegador (armadilhas/257).
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
// **E o passo 3 tem DOIS jeitos de falhar, que a tela nunca pode confundir.**
// O navegador pode não conseguir registrar o aparelho (falha do lado de lá,
// que esperar não cura), e o nosso servidor pode não confirmar (falha do lado
// de cá, que esperar cura). São duas frases diferentes no catálogo, e a função
// `inscrever` abaixo é onde a diferença se decide.
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
    ["convite", "ligado", "nao-deu", "sem-servico", "recusado"].forEach(function (
      cada
    ) {
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
      }, aparelhoNaoPode);
  }

  // O SEGUNDO argumento do `.then` acima, e não um `.catch` no fim: a
  // diferença é a lei desta função. Um `.catch` pendurado no fim pegaria
  // também a falha do `fetch` logo acima, e as duas falhas não são a mesma
  // coisa nem de longe:
  //
  //   · aqui o NAVEGADOR não conseguiu registrar o aparelho no serviço de push
  //     do fabricante. Tentar de novo amanhã dá no mesmo, porque nada do nosso
  //     lado mudou nem vai mudar;
  //   · lá em cima é o NOSSO servidor que não confirmou, e aí "tente de novo
  //     mais tarde" é conselho honesto.
  //
  // Enquanto as duas mostravam a mesma frase, quem usa um navegador que
  // bloqueia push de fábrica (o Brave, hoje) era mandado esperar para sempre.
  // O mantenedor bateu nisso em 02/09/2026 (`armadilhas/297`), e só descobriu
  // porque leu o erro no console: na tela, o site prometia que um dia ia dar.
  //
  // Não se olha a MENSAGEM do erro para decidir. Ela varia entre navegador e
  // versão, não é traduzida, e casá-la por texto seria uma régua que quebra
  // sozinha. O lugar onde a promessa quebrou já diz tudo.
  function aparelhoNaoPode() {
    return "sem-servico";
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
        // "default" — a pessoa fechou a caixa sem escolher. Ninguém decidiu
        // nada: o cartaz continua na tela, e o botão continua valendo.
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

        // O convite aparece como cartaz NOSSO, dentro da página. A caixa do
        // navegador, só o clique no botão abre — sem exceção. Não recrie um
        // caminho automático "onde o navegador deixa": foi ele que fez o
        // Malwarebytes bloquear o site inteiro em 31/08/2026 (armadilhas/257).
        mostrarSo("convite");
      });
    })
    .catch(function () {
      // Sem service worker pronto não há push nenhum. O site segue igual: o
      // aviso continua na caixa e no sininho, que é a verdade durável.
    });
})();
