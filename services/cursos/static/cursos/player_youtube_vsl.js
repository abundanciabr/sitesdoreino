(function () {
  "use strict";

  var apiCarregando = false;
  var filaApi = [];

  var SVG_PLAY =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M8 5v14l11-7z"/></svg>';
  var SVG_PAUSE =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6 5h4v14H6V5zm8 0h4v14h-4V5z"/></svg>';
  var SVG_FULLSCREEN =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M7 7h4V5H5v6h2V7zm10 0v4h2V5h-6v2h4zM7 17H5v6h6v-2H7v-4zm10 4h-4v2h6v-6h-2v4z"/></svg>';
  var SVG_FULLSCREEN_SAIR =
    '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M9 9H5V5h4v2H7v2zm6 0V7h-2V5h4v4h-2zm-6 6H7v-2H5v4h4v-2zm6 2h2v2h-4v-4h2v2z"/></svg>';

  function carregarApi() {
    if (window.YT && window.YT.Player) {
      return Promise.resolve();
    }
    if (apiCarregando) {
      return new Promise(function (resolve) {
        filaApi.push(resolve);
      });
    }
    apiCarregando = true;
    return new Promise(function (resolve) {
      var anterior = window.onYouTubeIframeAPIReady;
      window.onYouTubeIframeAPIReady = function () {
        if (typeof anterior === "function") {
          anterior();
        }
        filaApi.splice(0).forEach(function (cb) {
          cb();
        });
        resolve();
      };
      var tag = document.createElement("script");
      tag.src = "https://www.youtube.com/iframe_api";
      document.head.appendChild(tag);
    });
  }

  function rotuloPlay(pausado) {
    return pausado ? "Reproduzir" : "Pausar";
  }

  function sincronizarBotoes(raiz, player, botaoBarra, botaoGrande) {
    var estado = player.getPlayerState();
    var pausado =
      estado !== window.YT.PlayerState.PLAYING &&
      estado !== window.YT.PlayerState.BUFFERING;
    raiz.classList.toggle("em-reproducao", !pausado);
    botaoBarra.innerHTML = pausado ? SVG_PLAY : SVG_PAUSE;
    botaoBarra.setAttribute("aria-label", rotuloPlay(pausado));
    botaoGrande.innerHTML = pausado ? SVG_PLAY : SVG_PAUSE;
    botaoGrande.setAttribute("aria-label", rotuloPlay(pausado));
  }

  function alternarPlay(player, botaoBarra, botaoGrande, raiz) {
    var estado = player.getPlayerState();
    if (
      estado === window.YT.PlayerState.PLAYING ||
      estado === window.YT.PlayerState.BUFFERING
    ) {
      player.pauseVideo();
    } else {
      player.playVideo();
    }
    sincronizarBotoes(raiz, player, botaoBarra, botaoGrande);
  }

  function montar(raiz) {
    var idVideo = raiz.getAttribute("data-video-id");
    var alvo = raiz.querySelector(".vsl-youtube__mount");
    if (!idVideo || !alvo) {
      return;
    }

    var botaoBarra = raiz.querySelector(".vsl-youtube__toggle");
    var botaoGrande = raiz.querySelector(".vsl-youtube__bigplay");
    var botaoTelaCheia = raiz.querySelector(".vsl-youtube__tela-cheia");
    var quadro = raiz.querySelector(".vsl-youtube__quadro");

    var player = new window.YT.Player(alvo, {
      host: "https://www.youtube-nocookie.com",
      videoId: idVideo,
      playerVars: {
        autoplay: 0,
        cc_load_policy: 0,
        controls: 0,
        disablekb: 1,
        enablejsapi: 1,
        fs: 0,
        iv_load_policy: 3,
        modestbranding: 1,
        playsinline: 1,
        rel: 0,
      },
      events: {
        onReady: function () {
          player.getIframe().setAttribute("title", "Reprodutor de vídeo");
          player.getIframe().setAttribute("tabindex", "-1");
          desativarLegendas();
          sincronizarBotoes(raiz, player, botaoBarra, botaoGrande);
        },
        onApiChange: desativarLegendas,
        onStateChange: function () {
          desativarLegendas();
          sincronizarBotoes(raiz, player, botaoBarra, botaoGrande);
        },
      },
    });

    function desativarLegendas() {
      if (typeof player.unloadModule === "function" &&
          typeof player.getOptions === "function" &&
          player.getOptions().indexOf("captions") !== -1) {
        player.unloadModule("captions");
      }
    }

    function clicouPlay(evento) {
      evento.preventDefault();
      evento.stopPropagation();
      alternarPlay(player, botaoBarra, botaoGrande, raiz);
    }

    botaoBarra.addEventListener("click", clicouPlay);
    botaoGrande.addEventListener("click", clicouPlay);

    botaoTelaCheia.addEventListener("click", function (evento) {
      evento.preventDefault();
      evento.stopPropagation();
      if (document.fullscreenElement) {
        document.exitFullscreen();
        return;
      }
      if (quadro.requestFullscreen) {
        quadro.requestFullscreen();
      } else if (raiz.requestFullscreen) {
        raiz.requestFullscreen();
      }
    });

    function atualizarTelaCheia() {
      var ativo =
        document.fullscreenElement === quadro ||
        document.fullscreenElement === raiz;
      botaoTelaCheia.innerHTML = ativo ? SVG_FULLSCREEN_SAIR : SVG_FULLSCREEN;
      botaoTelaCheia.setAttribute(
        "aria-label",
        ativo ? "Sair da tela cheia" : "Tela cheia"
      );
    }

    document.addEventListener("fullscreenchange", atualizarTelaCheia);
    atualizarTelaCheia();

    raiz.addEventListener("contextmenu", function (evento) {
      evento.preventDefault();
    });
  }

  function iniciar() {
    var players = document.querySelectorAll("[data-vsl-youtube]");
    if (!players.length) {
      return;
    }
    carregarApi().then(function () {
      players.forEach(montar);
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", iniciar);
  } else {
    iniciar();
  }
})();


