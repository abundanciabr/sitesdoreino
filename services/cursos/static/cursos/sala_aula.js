(function () {
  "use strict";
  var layout = document.querySelector(".aula-layout");
  if (!layout) { return; }
  var painel = layout.querySelector(".conteudo-curso");
  var abrir = layout.querySelector(".abrir-conteudo");
  var fechar = layout.querySelector(".fechar-conteudo");
  if (!painel || !abrir || !fechar) { return; }
  fechar.hidden = false;
  abrir.setAttribute("aria-expanded", "true");
  function mostrar(ativo) {
    painel.hidden = !ativo;
    abrir.hidden = ativo;
    abrir.setAttribute("aria-expanded", String(ativo));
    layout.classList.toggle("conteudo-fechado", !ativo);
    (ativo ? fechar : abrir).focus();
  }
  fechar.addEventListener("click", function () { mostrar(false); });
  abrir.addEventListener("click", function () { mostrar(true); });
})();
