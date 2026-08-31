// static/funil/instalar.js — o convite "instale o app", e o registro do
// service worker que torna a instalação possível.
//
// A regra de produto, em uma frase: o convite aparece em CELULAR E TABLET, e
// nunca em computador. Quem está no PC já tem o site numa aba, e um cartaz
// pedindo para instalar seria só barulho — o Chrome de desktop, esse sim,
// continua oferecendo a instalação pelo botão dele na barra de endereço, o que
// não custa nada e não atrapalha ninguém.
//
// Os dois caminhos de instalação do mundo real, e por que existem dois blocos
// no template:
//
//   · Android/Chrome dispara `beforeinstallprompt` e deixa o site abrir a
//     caixa de instalação do sistema. É o caminho de um toque, e é o que o
//     bloco `data-modo="botao"` oferece.
//   · iPhone e iPad NÃO disparam evento nenhum: no Safari a instalação é
//     manual, pelo botão Compartilhar. Não há como automatizar, então o
//     honesto é ensinar o passo a passo, que é o bloco `data-modo="ios"`.
//
// E o convite só reaparece depois de um mês para quem disse "agora não"
// (`localStorage`). Pedir de novo na próxima página seria a mesma conversa
// que faz gente desinstalar app.

(function () {
  "use strict";

  var CHAVE_DA_DISPENSA = "meshcraft:instalar:silencio-ate";
  var DIAS_DE_SILENCIO = 30;

  var cartaz = document.getElementById("instalar-o-app");
  if (!cartaz) {
    return;
  }

  // ---------------------------------------------------------------------
  // O service worker. Registrado SEMPRE (inclusive no PC): ele é o que dá o
  // funcionamento sem rede, e sem ele o navegador não considera o site
  // instalável. O endereço leva a página inicial deste idioma — ver sw.js.
  // ---------------------------------------------------------------------
  if ("serviceWorker" in navigator) {
    var inicio = cartaz.getAttribute("data-inicio") || "/";
    window.addEventListener("load", function () {
      navigator.serviceWorker
        .register("/sw.js?inicio=" + encodeURIComponent(inicio))
        .catch(function () {
          // Falhou o registro, o site segue igual: nada nesta página depende
          // do service worker para funcionar. Falha ABERTA, como o sino.
        });
    });
  }

  // ---------------------------------------------------------------------
  // Quem vê o convite
  // ---------------------------------------------------------------------
  function jaEstaInstalado() {
    try {
      if (window.matchMedia("(display-mode: standalone)").matches) {
        return true;
      }
    } catch (e) {
      // matchMedia sem suporte: seguimos pelo caminho do Safari antigo.
    }
    return navigator.standalone === true;
  }

  var ua = navigator.userAgent || "";
  // iPad com iPadOS 13 ou mais novo se apresenta como "Macintosh": sem a
  // segunda metade deste teste, todo iPad ficaria sem convite nenhum.
  var ehIOS =
    /iPhone|iPad|iPod/.test(ua) ||
    (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);

  function ehComputador() {
    if (ehIOS) {
      return false;
    }
    if (/Android|Mobile|Tablet|Silk|Kindle|Opera Mini/i.test(ua)) {
      return false;
    }
    // Sem pista no user agent, decide o dedo: aparelho de toque sem sistema de
    // desktop declarado entra como celular/tablet.
    var toque = false;
    try {
      toque = window.matchMedia("(any-pointer: coarse)").matches;
    } catch (e) {
      toque = navigator.maxTouchPoints > 1;
    }
    return !(toque && !/Windows NT|Macintosh|X11|CrOS/.test(ua));
  }

  function estaEmSilencio() {
    try {
      var ate = window.localStorage.getItem(CHAVE_DA_DISPENSA);
      return ate !== null && Date.now() < Number(ate);
    } catch (e) {
      // Navegação privativa pode proibir o localStorage. Sem memória, o
      // convite aparece: melhor pedir de novo do que nunca pedir.
      return false;
    }
  }

  function silenciar() {
    try {
      window.localStorage.setItem(
        CHAVE_DA_DISPENSA,
        String(Date.now() + DIAS_DE_SILENCIO * 24 * 60 * 60 * 1000)
      );
    } catch (e) {
      // Sem memória disponível, o convite volta na próxima visita. Não é o
      // ideal, e é melhor que quebrar a página.
    }
  }

  function mostrar(modo) {
    var bloco = cartaz.querySelector('[data-modo="' + modo + '"]');
    if (!bloco) {
      return;
    }
    bloco.hidden = false;
    cartaz.hidden = false;
  }

  function esconder() {
    cartaz.hidden = true;
  }

  var depois = cartaz.querySelector('[data-acao="depois"]');
  if (depois) {
    depois.addEventListener("click", function () {
      silenciar();
      esconder();
    });
  }

  if (jaEstaInstalado() || ehComputador() || estaEmSilencio()) {
    return;
  }

  // ---------------------------------------------------------------------
  // Caminho 1: Android e qualquer navegador que ofereça a caixa do sistema
  // ---------------------------------------------------------------------
  var convite = null;
  var botao = cartaz.querySelector('[data-acao="instalar"]');

  window.addEventListener("beforeinstallprompt", function (evento) {
    // Sem o preventDefault o navegador mostraria a barra dele por cima da
    // nossa. Guardamos o evento para disparar a caixa no clique do botão:
    // depois deste retorno ele não pode mais ser usado uma segunda vez.
    evento.preventDefault();
    convite = evento;
    mostrar("botao");
  });

  if (botao) {
    botao.addEventListener("click", function () {
      if (!convite) {
        return;
      }
      convite.prompt();
      var pendente = convite;
      convite = null;
      esconder();
      if (pendente.userChoice && pendente.userChoice.then) {
        pendente.userChoice.then(function (escolha) {
          // Recusou a caixa do sistema: o mesmo silêncio de quem clicou
          // "agora não". Insistir na página seguinte é a receita de irritar.
          if (!escolha || escolha.outcome !== "accepted") {
            silenciar();
          }
        });
      }
    });
  }

  window.addEventListener("appinstalled", function () {
    esconder();
    try {
      window.localStorage.removeItem(CHAVE_DA_DISPENSA);
    } catch (e) {
      // Nada a fazer, e nada quebra: quem instalou não vê mais o convite,
      // porque `jaEstaInstalado` passa a ser verdadeiro.
    }
  });

  // ---------------------------------------------------------------------
  // Caminho 2: iPhone e iPad, onde não existe evento nenhum para esperar
  // ---------------------------------------------------------------------
  if (ehIOS) {
    // Só no Safari: dentro do Chrome ou do Firefox do iPhone o menu
    // Compartilhar não tem "Adicionar à Tela de Início", e ensinar um passo
    // que não existe é pior do que ficar calado.
    var safari = !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua);
    if (safari) {
      mostrar("ios");
    }
  }
})();
