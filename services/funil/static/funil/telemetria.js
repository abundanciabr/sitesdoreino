// static/funil/telemetria.js: conta a secao que apareceu na tela e o clique no
// botao da oferta, e manda os dois para POST /telemetria.
//
// Medir nunca atrasa nem quebra a pagina. Todo envio sai por sendBeacon (ou
// fetch com keepalive), que nao segura a navegacao do clique, e todo erro e
// engolido: medicao pode falhar, a pagina nao.
//
// O script so conhece o contexto que o servidor assinou na renderizacao. Quem e
// o visitante o servidor le do cookie, que este script nem consegue ler.
(function () {
  var script = document.currentScript;
  var contexto = script && script.getAttribute("data-contexto");
  if (!contexto) return;

  function enviar(fato) {
    fato.contexto = contexto;
    var corpo = JSON.stringify(fato);
    try {
      if (navigator.sendBeacon && navigator.sendBeacon("/telemetria", corpo)) return;
    } catch (erro) {}
    try {
      fetch("/telemetria", {
        method: "POST",
        body: corpo,
        keepalive: true,
        credentials: "same-origin",
      }).catch(function () {});
    } catch (erro) {}
  }

  // Uma vez por secao e por carga: depois do primeiro aparecimento a secao
  // sai do observador, e rolar para cima e voltar nao conta de novo.
  if ("IntersectionObserver" in window) {
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (!entrada.isIntersecting) return;
        observador.unobserve(entrada.target);
        enviar({ evento: "secao-vista", secao: entrada.target.getAttribute("data-secao") });
      });
    });
    document.querySelectorAll("[data-secao]").forEach(function (secao) {
      observador.observe(secao);
    });
  }

  document.addEventListener("click", function (evento) {
    var botao = evento.target.closest && evento.target.closest("a.cta[data-slot]");
    var secao = botao && botao.closest("[data-secao]");
    if (!secao) return;
    enviar({
      evento: "cta-clicado",
      secao: secao.getAttribute("data-secao"),
      slot: botao.getAttribute("data-slot"),
      destino: botao.getAttribute("data-destino"),
    });
  });
})();
