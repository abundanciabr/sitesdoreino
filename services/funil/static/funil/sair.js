(function () {
  "use strict";
  // Normal POST remains available if JavaScript is unavailable.
  document.querySelectorAll('form[action="/entrar/sair"]').forEach(function (form) {
    var pending = false;
    var button = form.querySelector('button[type="submit"]');
    var status = form.querySelector('[data-saida-status]');
    if (!button || !status || !window.fetch || !window.AbortController) return;
    var label = button.textContent;
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      if (pending) return;
      pending = true;
      button.disabled = true;
      button.textContent = "Saindo…";
      status.textContent = " Encerrando sua sessão.";
      var controller = new AbortController();
      var timer = setTimeout(function () { controller.abort(); }, 15000);
      try {
        // Cancel this page's session renewal before requesting logout.
        document.querySelectorAll('iframe[src="/entrar/manter/"]').forEach(function (frame) { frame.remove(); });
        var response = await fetch(form.action, {
          method: "POST", credentials: "same-origin", cache: "no-store",
          headers: { "Accept": "application/json" },
          body: new URLSearchParams(new FormData(form)), signal: controller.signal
        });
        if (!response.ok) throw new Error("logout failed");
        var result = await response.json();
        if (result.saiu !== true) throw new Error("logout unconfirmed");
        status.textContent = " Você saiu da conta.";
        var destination = new URL(result.destino || "/", window.location.origin);
        if (destination.origin !== window.location.origin) destination = new URL("/", window.location.origin);
        destination.searchParams.set("saiu", "1");
        window.location.replace(destination.href);
      } catch (error) {
        status.textContent = " Não foi possível sair agora. Clique em Sair para tentar novamente.";
        button.disabled = false;
        button.textContent = label;
        pending = false;
      } finally {
        clearTimeout(timer);
      }
    });
  });
  // Do not restore an authenticated snapshot from the browser's back cache.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) window.location.reload();
  });
})();
