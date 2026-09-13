(() => {
  const lista = document.getElementById("radio-mensagens");
  const aviso = document.getElementById("radio-aviso");
  let ultima = Number(lista.dataset.ultima);
  const ler = async () => {
    try {
      const resposta = await fetch(`${lista.dataset.api}?desde=${ultima}`, {headers: {Accept: "application/json"}});
      if (!resposta.ok) throw new Error("leitura indisponível");
      const dados = await resposta.json();
      if (!Array.isArray(dados.mensagens)) throw new Error("resposta inválida");
      if (dados.mensagens.length && lista.querySelector(".aviso")) lista.replaceChildren();
      dados.mensagens.forEach((mensagem) => {
        const artigo = document.createElement("article");
        artigo.className = "cartao radio-mensagem";
        const autoria = document.createElement("div");
        autoria.textContent = `${mensagem.autor} · ${mensagem.quando}${mensagem.tarefa ? ` · ${mensagem.tarefa}` : ""}`;
        const texto = document.createElement("p");
        texto.textContent = mensagem.texto;
        artigo.append(autoria, texto);
        lista.appendChild(artigo);
        ultima = Math.max(ultima, mensagem.sequencia);
      });
      aviso.hidden = true;
    } catch (_) {
      aviso.textContent = "A atualização automática falhou. Confira a conexão; tentaremos novamente em instantes. Seu texto continua no formulário.";
      aviso.hidden = false;
    } finally {
      setTimeout(ler, 3000);
    }
  };
  setTimeout(ler, 3000);
})();
