(() => {
  const lista = document.getElementById("radio-mensagens");
  const aviso = document.getElementById("radio-aviso");
  let ultima = Number(lista.dataset.ultima);
  const ler = async () => {
    try {
      const resposta = await fetch(`${lista.dataset.api}?desde=${ultima}`, {headers: {Accept: "application/json"}});
      if (!resposta.ok) throw new Error("leitura indisponível");
      const dados = await resposta.json();
      if (!Array.isArray(dados.mensagens) || dados.mensagens.some((mensagem) => !["recado", "parecer", "boletim"].includes(mensagem.tipo || "recado"))) throw new Error("resposta inválida");
      if (dados.mensagens.length && lista.querySelector(".aviso")) lista.replaceChildren();
      dados.mensagens.forEach((mensagem) => {
        const tipo = mensagem.tipo || "recado";
        const artigo = document.createElement(tipo === "boletim" ? "p" : "article");
        artigo.className = `${tipo === "boletim" ? "nota" : tipo === "parecer" ? "historia" : "cartao"} radio-mensagem`;
        if (tipo === "boletim") {
          const linha = document.createElement("span");
          linha.className = "subtitulo";
          linha.textContent = `Boletim · ${mensagem.autor} · ${mensagem.texto}`;
          artigo.appendChild(linha);
          lista.appendChild(artigo);
          ultima = Math.max(ultima, mensagem.sequencia);
          return;
        }
        const autoria = document.createElement("div");
        autoria.textContent = `${tipo === "parecer" ? "Parecer" : "Recado"} · ${mensagem.autor} · ${mensagem.quando}${mensagem.tarefa ? ` · ${mensagem.tarefa}` : ""}`;
        const texto = document.createElement("p");
        texto.textContent = mensagem.texto;
        artigo.appendChild(autoria);
        if (tipo === "parecer") {
          const legenda = document.createElement("p");
          legenda.className = "nota";
          legenda.textContent = "Comentário, sem ordem de execução";
          artigo.appendChild(legenda);
        }
        artigo.appendChild(texto);
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
