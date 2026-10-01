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

  var SVG_VOLUME = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 4V5L7 9H3zm12-1v8a5 5 0 000-8zm0-4v2a7 7 0 010 12v2a9 9 0 000-16z"/></svg>';
  var SVG_MUDO = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 9v6h4l5 4V5L7 9H3zm12.4-.4L14 10l3 3-3 3 1.4 1.4 3-3 3 3L23 16l-3-3 3-3-1.6-1.4-3 3-3-3z"/></svg>';
  var SVG_CINEMA = '<svg viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M3 5h18v14H3V5zm2 3v8h14V8H5z"/></svg>';

  function tempo(segundos) {
    var total = Math.max(0, Math.floor(segundos || 0));
    var horas = Math.floor(total / 3600);
    var minutos = Math.floor(total / 60) % 60;
    var resto = String(total % 60).padStart(2, "0");
    return horas ? horas + ":" + String(minutos).padStart(2, "0") + ":" + resto : minutos + ":" + resto;
  }

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
    var barraProgresso = raiz.querySelector(".vsl-youtube__progresso");
    var relogio = raiz.querySelector(".vsl-youtube__tempo");
    var volume = raiz.querySelector(".vsl-youtube__volume");
    var botaoMudo = raiz.querySelector(".vsl-youtube__mudo");
    var velocidade = raiz.querySelector(".vsl-youtube__velocidade");
    var botaoCinema = raiz.querySelector(".vsl-youtube__cinema");
    var pronto = false;
    var buscando = false;
    var ultimoVolume = 100;
    var intervalo;
    botaoGrande.disabled = true;
    botaoMudo.innerHTML = SVG_VOLUME;
    botaoCinema.innerHTML = SVG_CINEMA;

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
          pronto = true;
          botaoGrande.disabled = false;
          botaoBarra.disabled = false;
          botaoMudo.disabled = false;
          volume.disabled = false;
          velocidade.disabled = false;
          atualizarControles();
          intervalo = window.setInterval(atualizarControles, 500);
          desativarLegendas();
          sincronizarBotoes(raiz, player, botaoBarra, botaoGrande);
        },
        onApiChange: desativarLegendas,
        onPlaybackRateChange: atualizarControles,
        onStateChange: function () {
          atualizarControles();
          desativarLegendas();
          sincronizarBotoes(raiz, player, botaoBarra, botaoGrande);
        },
      },
    });

    function atualizarControles() {
      if (!pronto || !raiz.isConnected) { return; }
      var duracao = player.getDuration() || 0;
      var atual = Math.min(player.getCurrentTime() || 0, duracao);
      barraProgresso.disabled = duracao <= 0;
      barraProgresso.max = Math.floor(duracao);
      if (!buscando) { barraProgresso.value = Math.floor(atual); }
      var mostrado = buscando ? Number(barraProgresso.value) : atual;
      barraProgresso.style.setProperty("--progresso", (duracao ? mostrado / duracao * 100 : 0) + "%");
      barraProgresso.setAttribute("aria-valuetext", tempo(mostrado) + " de " + tempo(duracao));
      relogio.textContent = tempo(mostrado) + " / " + tempo(duracao);
      var silenciado = player.isMuted() || player.getVolume() === 0;
      botaoMudo.innerHTML = silenciado ? SVG_MUDO : SVG_VOLUME;
      botaoMudo.setAttribute("aria-label", silenciado ? "Ativar som" : "Silenciar");
      botaoMudo.setAttribute("aria-pressed", String(silenciado));
      if (document.activeElement !== volume) { volume.value = silenciado ? 0 : player.getVolume(); }
      var disponiveis = player.getAvailablePlaybackRates();
      Array.from(velocidade.options).forEach(function (opcao) {
        opcao.disabled = disponiveis.indexOf(Number(opcao.value)) === -1;
      });
      velocidade.value = String(player.getPlaybackRate());
    }

    barraProgresso.addEventListener("input", function () {
      buscando = true;
      atualizarControles();
    });
    barraProgresso.addEventListener("change", function () {
      if (pronto) { player.seekTo(Number(barraProgresso.value), true); }
      buscando = false;
    });
    barraProgresso.addEventListener("blur", function () { buscando = false; });
    volume.addEventListener("input", function () {
      if (!pronto) { return; }
      var valor = Number(volume.value);
      player.setVolume(valor);
      if (valor > 0) { ultimoVolume = valor; player.unMute(); } else { player.mute(); }
      atualizarControles();
    });
    botaoMudo.addEventListener("click", function () {
      if (!pronto) { return; }
      if (player.isMuted() || player.getVolume() === 0) {
        player.setVolume(ultimoVolume);
        player.unMute();
      } else {
        ultimoVolume = player.getVolume();
        player.mute();
      }
      atualizarControles();
    });
    velocidade.addEventListener("change", function () {
      if (pronto) { player.setPlaybackRate(Number(velocidade.value)); }
    });

    function cinema(ativo) {
      document.body.classList.toggle("vsl-modo-cinema", ativo);
      botaoCinema.setAttribute("aria-pressed", String(ativo));
      botaoCinema.setAttribute("aria-label", ativo ? "Sair do modo cinema" : "Modo cinema");
    }
    botaoCinema.addEventListener("click", function () {
      cinema(botaoCinema.getAttribute("aria-pressed") !== "true");
    });
    document.addEventListener("keydown", function (evento) {
      if (evento.key === "Escape" && !document.fullscreenElement) { cinema(false); }
    });
    window.addEventListener("pagehide", function () { window.clearInterval(intervalo); });
    window.addEventListener("pageshow", function (evento) {
      if (evento.persisted && pronto) { intervalo = window.setInterval(atualizarControles, 500); }
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


