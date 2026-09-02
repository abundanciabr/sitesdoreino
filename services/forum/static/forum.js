// =============================================================================
// O RASCUNHO DA IA APARECENDO AO VIVO — o primeiro JavaScript de uma página
// pública deste site, e ele foi desenhado para poder falhar.
//
// Pedido do mantenedor em 02/09/2026: *"quero o streaming da resposta sendo
// gerada na tela ao vivo para facilitar o feedback visual"*. A razão é boa e não
// é enfeite: sem ele o botão fica alguns segundos parecendo travado, e foi
// exatamente esse silêncio que o levou a achar que nada tinha acontecido.
//
// A REGRA QUE ORGANIZA O ARQUIVO INTEIRO: melhoria progressiva. O formulário da
// caixa "Rascunhar com a IA" é um `<form>` normal, e continua sendo. Este script
// só INTERCEPTA o envio. Se ele não carregar, se o navegador não tiver as peças,
// ou se a chamada ao vivo falhar, o formulário faz o que sempre fez: manda o
// POST, a página recarrega, e o rascunho chega inteiro de uma vez. Nada aqui é o
// único caminho para nada.
// =============================================================================
(function () {
  "use strict";

  var caixa = document.getElementById("ia-rascunho");
  if (!caixa) return; // quem não modera não recebe a caixa: nada a fazer.

  var textoDaResposta = document.getElementById("texto");
  var botao = caixa.querySelector("button[type=submit]");
  var recado = document.getElementById("ia-recado");
  var endereco = caixa.getAttribute("data-ao-vivo");

  // AS PEÇAS DO NAVEGADOR, conferidas antes de prometer qualquer coisa.
  // `fetch` sem `body.getReader` existe em navegador antigo: ele baixaria tudo e
  // entregaria no fim, o que daria uma experiência PIOR que a do formulário
  // (a mesma espera, e sem o recarregamento que ao menos mostra o resultado).
  var temFluxo =
    typeof window.fetch === "function" &&
    typeof window.TextDecoder === "function" &&
    typeof window.ReadableStream === "function";

  if (!textoDaResposta || !botao || !endereco || !temFluxo) return;

  // Quando o caminho ao vivo falha, ele se aposenta e devolve o volante ao
  // formulário. É por isso que a bandeira existe em vez de um
  // `removeEventListener`: o próximo clique tem de seguir o caminho normal
  // inteiro, incluindo o recarregamento da página.
  var aoVivoQuebrou = false;

  function dizer(frase, ehErro) {
    if (!recado) return;
    recado.textContent = frase;
    recado.className = ehErro ? "erro" : "sub";
  }

  caixa.addEventListener("submit", function (evento) {
    if (aoVivoQuebrou) return; // deixa o `<form>` fazer o de sempre.
    evento.preventDefault();

    var dados = new FormData(caixa); // leva o token de CSRF junto
    var rotuloDeAntes = botao.textContent;
    botao.disabled = true;
    botao.textContent = "Escrevendo...";
    dizer("A IA está escrevendo. O texto vai aparecendo na caixa aqui embaixo.", false);

    // A caixa começa VAZIA e o cursor vai para ela: assim o texto nasce onde a
    // pessoa está olhando, que é o problema inteiro que este arquivo resolve.
    textoDaResposta.value = "";
    textoDaResposta.focus();

    function terminar() {
      botao.disabled = false;
      botao.textContent = rotuloDeAntes;
    }

    fetch(endereco, {
      method: "POST",
      body: dados,
      credentials: "same-origin",
    })
      .then(function (resposta) {
        if (!resposta.ok || !resposta.body) {
          throw new Error("HTTP " + resposta.status);
        }
        var leitor = resposta.body.getReader();
        var decodificador = new TextDecoder("utf-8");
        var sobra = "";

        // O servidor manda UMA LINHA JSON por pedaço. Linha é o quadro mais
        // simples que sobrevive a um pedaço partido no meio pela rede, e a
        // `sobra` é o que guarda essa metade até a outra chegar.
        function engolir(linha) {
          if (!linha) return;
          var pedaco;
          try {
            pedaco = JSON.parse(linha);
          } catch (e) {
            return; // linha partida ou ruído: ignorar é melhor que quebrar.
          }
          if (pedaco.erro) {
            dizer(pedaco.erro, true);
          } else if (typeof pedaco.t === "string") {
            textoDaResposta.value += pedaco.t;
            // Rolar junto com o texto: sem isto a caixa cresce e o que está
            // sendo escrito some para baixo da borda.
            textoDaResposta.scrollTop = textoDaResposta.scrollHeight;
          } else if (pedaco.fim) {
            dizer(pedaco.fim, false);
          }
        }

        function proximo() {
          return leitor.read().then(function (bloco) {
            if (bloco.done) {
              engolir(sobra.trim());
              return;
            }
            sobra += decodificador.decode(bloco.value, { stream: true });
            var linhas = sobra.split("\n");
            sobra = linhas.pop();
            linhas.forEach(function (linha) {
              engolir(linha.trim());
            });
            return proximo();
          });
        }
        return proximo();
      })
      .then(terminar)
      .catch(function (erro) {
        // FALHA DO CAMINHO AO VIVO NÃO PODE CUSTAR O RASCUNHO.
        aoVivoQuebrou = true;
        dizer(
          "Não consegui mostrar ao vivo (" +
            erro.message +
            "). Aperte o botão de novo: o texto chega de uma vez, como antes.",
          true
        );
        terminar();
      });
  });
})();
