let chromium;
try {
  ({ chromium } = require("playwright"));
} catch (erro) {
  throw new Error(
    "Playwright não está instalado; execute npm install --no-save --no-package-lock playwright em services/forum."
  );
}

// Teto de passos de Tab antes de desistir de achar o alvo: alto o bastante
// para qualquer header futuro, baixo o bastante para nunca virar um laço
// silencioso (o mesmo raciocínio de `esperarTelemetria` no molde do quiz).
const TETO_DE_TAB = 25;

function focoEVisivel(info) {
  return info.outlineStyle !== "none" || info.boxShadow !== "none";
}

/** Tab a partir do topo da página até o elemento que `bate` aceita.
 *
 * Devolve quantos passos custou e se TODO elemento focado no caminho (não só
 * o alvo final) tinha contorno visível: é o que o brief pede, "cada
 * elemento focado tem contorno visível". */
async function tabAte(page, bate) {
  await page.evaluate(() => document.activeElement && document.activeElement.blur());
  const caminho = [];
  for (let passo = 1; passo <= TETO_DE_TAB; passo++) {
    await page.keyboard.press("Tab");
    const info = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const estilo = getComputedStyle(el);
      return {
        tag: el.tagName,
        texto: (el.innerText || el.value || "").trim(),
        outlineStyle: estilo.outlineStyle,
        boxShadow: estilo.boxShadow,
      };
    });
    if (!info) continue;
    caminho.push(info);
    if (bate(info)) {
      return {
        passos: passo,
        focoSempreVisivel: caminho.every(focoEVisivel),
        alvo: info.texto,
        caminho,
      };
    }
  }
  throw new Error(
    `Tab não alcançou o alvo em ${TETO_DE_TAB} passos. Caminho: ${JSON.stringify(caminho)}`
  );
}

async function semRolagemLateral(page) {
  return page.evaluate(
    () => document.scrollingElement.scrollWidth <= window.innerWidth
  );
}

async function main() {
  const base = new URL(process.argv[2]);
  const host = process.argv[3];
  const slugDoGrupo = process.argv[4];
  const cookie = process.argv[5];
  const pastaDeCapturas = process.argv[6];
  if (!base.port || !host || !slugDoGrupo || !cookie || !pastaDeCapturas) {
    throw new Error(
      "Uso: node comunidade_browser.js <live-server-url> <host> <slug-do-grupo> <cookie> <pasta-de-capturas>"
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
    const context = await browser.newContext({ viewport: { width: 390, height: 844 } });
    await context.addCookies([
      {
        name: "meshcraft_sessao",
        value: cookie,
        domain: host,
        path: "/",
      },
    ]);
    const page = await context.newPage();
    page.on("pageerror", (erro) => erros.push(`página: ${erro.message}`));
    page.on("console", (mensagem) => {
      if (mensagem.type() === "error") erros.push(`console: ${mensagem.text()}`);
    });
    page.on("response", (resposta) => {
      if (resposta.status() >= 400) erros.push(`HTTP ${resposta.status()}: ${resposta.url()}`);
    });

    // TELA 1: /comunidade, o membro do grupo, e o link que leva a pedir ajuda
    // é o alvo do teclado (é literalmente a porta para a tela 3).
    const enderecoComunidade = `${base.protocol}//${host}:${base.port}/comunidade`;
    const cargaComunidade = await page.goto(enderecoComunidade, { waitUntil: "networkidle" });
    if (!cargaComunidade || cargaComunidade.status() !== 200) {
      throw new Error("A Comunidade não abriu com HTTP 200.");
    }
    if (await page.locator("h1").innerText() !== "Comunidade") {
      throw new Error("O título da Comunidade não apareceu.");
    }
    const linkDoGrupo = page.getByRole("link", { name: "Apresente-se ao grupo ou peça ajuda" });
    if (!(await linkDoGrupo.isVisible())) {
      throw new Error("O link para pedir ajuda ao grupo não está visível na Comunidade.");
    }
    await page.screenshot({ path: `${pastaDeCapturas}/comunidade.png` });
    const scrollComunidade = await semRolagemLateral(page);
    const tabComunidade = await tabAte(
      page,
      (info) => info.tag === "A" && info.texto === "Apresente-se ao grupo ou peça ajuda"
    );

    // TELA 2 e 3: a página do grupo (Area TURMA), e dentro dela o pedido de
    // ajuda ao grupo é a MESMA tela, na caixa "Abrir uma conversa" (a view não
    // separa as duas: `apps/core/views.contexto_da_area`). O alvo do teclado
    // aqui é o botão que publica o pedido.
    const enderecoGrupo = `${base.protocol}//${host}:${base.port}/a/${slugDoGrupo}`;
    const cargaGrupo = await page.goto(enderecoGrupo, { waitUntil: "networkidle" });
    if (!cargaGrupo || cargaGrupo.status() !== 200) {
      throw new Error("A página do grupo não abriu com HTTP 200.");
    }
    await page.screenshot({ path: `${pastaDeCapturas}/grupo.png` });
    if (!(await page.getByText("Como pedir ajuda ao grupo").isVisible())) {
      throw new Error("O molde de pedido de ajuda não apareceu na área do grupo.");
    }
    const campoTitulo = page.getByLabel("Sua pergunta em uma linha");
    const campoTexto = page.getByLabel("Conte com calma");
    if ((await campoTitulo.count()) !== 1 || !(await campoTitulo.isVisible())) {
      throw new Error("O campo do título do pedido de ajuda não tem rótulo acessível único.");
    }
    if ((await campoTexto.count()) !== 1 || !(await campoTexto.isVisible())) {
      throw new Error("O campo do texto do pedido de ajuda não tem rótulo acessível único.");
    }
    await campoTitulo.scrollIntoViewIfNeeded();
    await page.screenshot({ path: `${pastaDeCapturas}/pedir_ajuda.png` });
    const scrollGrupo = await semRolagemLateral(page);
    const tabGrupo = await tabAte(
      page,
      (info) => info.tag === "BUTTON" && info.texto === "Publicar"
    );

    if (erros.length) {
      throw new Error(`Erros inesperados no navegador ou servidor: ${erros.join(" | ")}`);
    }

    console.log(
      JSON.stringify({
        comunidade: {
          scrollOk: scrollComunidade,
          passosDeTab: tabComunidade.passos,
          focoSempreVisivel: tabComunidade.focoSempreVisivel,
          alvo: tabComunidade.alvo,
        },
        grupo: {
          scrollOk: scrollGrupo,
          passosDeTab: tabGrupo.passos,
          focoSempreVisivel: tabGrupo.focoSempreVisivel,
          alvo: tabGrupo.alvo,
          rotulos: { titulo: true, texto: true },
        },
      })
    );
  } finally {
    await browser.close();
  }
}

main().catch((erro) => {
  console.error(erro.stack || erro.message);
  process.exitCode = 1;
});
