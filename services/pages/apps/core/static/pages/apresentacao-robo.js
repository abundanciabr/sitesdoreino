(() => {
  "use strict";
  const form = document.getElementById("apresentacao");
  if (!form) return;
  const salvar = document.getElementById("salvar-apresentacao");
  let pendentes = 0;
  for (const botao of form.querySelectorAll("[data-gerar]")) {
    botao.addEventListener("click", async () => {
      const campo = document.getElementById(botao.dataset.gerar);
      const status = document.getElementById("status-" + campo.id);
      const rotulo = botao.textContent;
      const dados = new FormData(form);
      dados.set("campo", campo.name);
      pendentes++;
      salvar.disabled = true;
      botao.disabled = true;
      campo.readOnly = true;
      botao.textContent = "Gerando...";
      status.textContent = "Preparando um exemplo para você...";
      try {
        const resposta = await fetch(form.dataset.gerador, {
          method: "POST",
          credentials: "same-origin",
          headers: {"X-CSRFToken": dados.get("csrfmiddlewaretoken")},
          body: dados
        });
        let resultado;
        try { resultado = await resposta.json(); }
        catch (_) { throw new Error("Não foi possível gerar agora. Seu texto foi mantido."); }
        if (!resposta.ok || typeof resultado.texto !== "string" || !resultado.texto.trim()) {
          throw new Error(resultado.erro || "Não foi possível gerar agora. Seu texto foi mantido.");
        }
        campo.value = resultado.texto;
        campo.dispatchEvent(new Event("input", {bubbles: true}));
        botao.textContent = "Gerar novamente";
        status.textContent = "Exemplo pronto. Você pode editar e salvar.";
        campo.focus();
      } catch (erro) {
        botao.textContent = rotulo;
        status.textContent = erro.message;
      } finally {
        pendentes--;
        salvar.disabled = pendentes > 0;
        botao.disabled = false;
        campo.readOnly = false;
      }
    });
  }
})();
