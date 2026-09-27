let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (erro) {
  throw new Error(
    "Playwright não está instalado; execute npm install --no-save --no-package-lock playwright em services/gamificacao."
  );
}

const MAXIMO_DE_PASSOS = 30;

async function main() {
  const baseUrl = (process.argv[2] || "").replace(/\/$/, "");
  const caminho = process.argv[3];
  const tagAlvo = (process.argv[4] || "").toLowerCase();
  const textoAlvo = process.argv[5];
  const capturaEm = process.argv[6]; // opcional: caminho do PNG de evidência
  if (!baseUrl || !caminho || !tagAlvo || !textoAlvo) {
    throw new Error(
      "Uso: node comunidade_browser.js <live-server-url> <caminho> <tag-alvo> <texto-alvo> [captura.png]"
    );
  }

  let browser;
  try {
    browser = await chromium.launch();
  } catch (erro) {
    throw new Error(`Não consegui abrir o Chromium do Playwright: ${erro.message}`);
  }

  const erros = [];
  try {
    const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
    page.on("pageerror", erro => erros.push(`página: ${erro.message}`));
    page.on("console", mensagem => {
      if (mensagem.type() === "error") erros.push(`console: ${mensagem.text()}`);
    });

    const endereco = `${baseUrl}${caminho}`;
    const carregamento = await page.goto(endereco, { waitUntil: "networkidle" });
    if (!carregamento || carregamento.status() !== 200) {
      throw new Error(
        `A tela não abriu com HTTP 200: ${carregamento ? carregamento.status() : "sem resposta"}.`
      );
    }

    const medida = await page.evaluate(() => ({
      scrollWidth: document.scrollingElement.scrollWidth,
      innerWidth: window.innerWidth,
    }));

    // A partir do topo, só com Tab: cada passo grava o elemento focado, se o
    // contorno dele é visível, e se ele já é o alvo dentro do <main>. O
    // contorno conta como visível por outline OU por box-shadow calculado
    // diferente de "none", porque a folha de estilo desta célula usa outline
    // (a:focus-visible), e um guarda que só aceitasse outline reprovaria uma
    // troca de estilo que ainda deixa o foco visível.
    const sequencia = [];
    let passosAteOAlvo = 0;
    let alvoEncontrado = false;
    let focoVisivelEmTodosOsPassos = true;

    for (let passo = 1; passo <= MAXIMO_DE_PASSOS; passo += 1) {
      await page.keyboard.press("Tab");
      const estadoDoFoco = await page.evaluate(() => {
        const elemento = document.activeElement;
        if (!elemento || elemento === document.body) return null;
        const estilo = getComputedStyle(elemento);
        const outlineVisivel =
          estilo.outlineStyle !== "none" && parseFloat(estilo.outlineWidth) > 0;
        const sombraVisivel =
          estilo.boxShadow !== "none" && estilo.boxShadow.trim() !== "";
        return {
          tag: elemento.tagName.toLowerCase(),
          texto: (elemento.textContent || "").trim(),
          dentroDoMain: Boolean(elemento.closest("main")),
          focoVisivel: outlineVisivel || sombraVisivel,
        };
      });
      if (!estadoDoFoco) {
        throw new Error(`O Tab número ${passo} perdeu o foco (voltou ao body ou saiu da página).`);
      }
      sequencia.push(estadoDoFoco);
      if (!estadoDoFoco.focoVisivel) focoVisivelEmTodosOsPassos = false;
      if (
        estadoDoFoco.dentroDoMain &&
        estadoDoFoco.tag === tagAlvo &&
        estadoDoFoco.texto === textoAlvo
      ) {
        passosAteOAlvo = passo;
        alvoEncontrado = true;
        break;
      }
    }

    const textoDaPagina = await page.locator("body").innerText();

    if (capturaEm) {
      // Evidência visual, com o foco já no alvo: mostra os 390 px e o
      // contorno de foco na mesma imagem que o PR anexa.
      await page.screenshot({ path: capturaEm });
    }

    if (erros.length) throw new Error(`Erros inesperados no navegador: ${erros.join(" | ")}`);

    console.log(
      JSON.stringify({
        url: endereco,
        scroll_width: medida.scrollWidth,
        inner_width: medida.innerWidth,
        passos_ate_o_alvo: passosAteOAlvo,
        passos_maximos: MAXIMO_DE_PASSOS,
        alvo_encontrado: alvoEncontrado,
        foco_visivel_em_todos_os_passos: focoVisivelEmTodosOsPassos,
        sequencia,
        texto_da_pagina: textoDaPagina,
      })
    );
  } finally {
    await browser.close();
  }
}

main().catch(erro => {
  console.error(erro.stack || erro.message);
  process.exitCode = 1;
});
