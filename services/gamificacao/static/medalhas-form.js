(() => {
  const script = document.currentScript;
  const form = document.getElementById("form-medalha");
  if (!form || !script) return;
  document.getElementById("ver-medalha").addEventListener("click", () => {
    const url = new URL(script.dataset.previaUrl, location.origin);
    url.searchParams.set("nome", document.getElementById("nome-medalha").value);
    url.searchParams.set("mensagem", document.getElementById("mensagem-medalha").value);
    document.getElementById("previa-medalha").src = url.href;
  });
  form.addEventListener("submit", () => {
    const botao = form.querySelector("[type=submit]");
    botao.disabled = true; botao.textContent = "Entregando medalha…";
  });
})();
