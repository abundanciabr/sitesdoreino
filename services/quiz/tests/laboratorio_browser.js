const path = require("path");
const { chromium } = require("playwright");

async function main() {
  const base = process.argv[2];
  const cookies = JSON.parse(process.env.LAB_COOKIES);
  const browser = await chromium.launch();
  const provas = [];
  try {
    for (const tamanho of [{width:390,height:844},{width:1280,height:800}]) {
      for (let posicao = 0; posicao < 3; posicao++) {
        const context = await browser.newContext({viewport:tamanho});
        const page = await context.newPage();
        await context.addCookies([{name:"quiz_session",value:cookies[(tamanho.width===390 ? 0 : 3)+posicao],url:base}]);
        const erros = [];
        page.on("pageerror", erro => erros.push(erro.message));
        await page.goto(`${base}/laboratorio-crivo/`, {waitUntil:"networkidle"});
        if (posicao === 0) await page.screenshot({path:path.join(process.env.LAB_PROVAS,`formulario-${tamanho.width}.png`),fullPage:true});
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("O formulário excedeu a largura da tela.");
        await page.getByRole("button",{name:"Continuar"}).click();
        if (!await page.locator("fieldset.ativo [data-validacao]").isVisible()) throw new Error("Pergunta vazia avançou.");
        for (let pergunta=0; pergunta<3; pergunta++) {
          const radio = page.locator("fieldset.ativo input[type=radio]").nth(posicao);
          await radio.focus();
          await page.keyboard.press("Space");
          await page.getByRole("button", {name:"Continuar"}).focus();
          await page.keyboard.press("Enter");
        }
        await page.getByLabel("E-mail", {exact:true}).fill("laboratorio.crivo@exemplo.test");
        await page.getByLabel("Nome").fill("Laboratório Crivo");
        await page.getByRole("button",{name:"Ver resultado"}).focus();
        await page.keyboard.press("Enter");
        const titulo = ["Escolha um projeto para começar","Proteja seu ritmo de execução","Feche e compartilhe sua entrega"][posicao];
        await page.getByRole("heading",{name:titulo,exact:true}).waitFor();
        if (posicao === 2) await page.screenshot({path:path.join(process.env.LAB_PROVAS,`resultado-${tamanho.width}.png`),fullPage:true});
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("O resultado excedeu a largura da tela.");
        const resultado = page.url();
        await page.goto(`${base}/laboratorio-crivo/`);
        if (page.url() !== resultado) throw new Error("Retorno não conservou resultado.");
        await page.goto(`${base}/laboratorio-crivo/observacao/`);
        await page.getByText(`Pontuação calculada pelo servidor:`,{exact:false}).waitFor();
        const observacao = await page.locator("main").innerText();
        if (posicao === 2) await page.screenshot({path:path.join(process.env.LAB_PROVAS,`observacao-${tamanho.width}.png`),fullPage:true});
        if (observacao.includes("laboratorio.crivo@") || observacao.includes("session_id")) throw new Error("Observação expôs contato ou sessão.");
        if (await page.evaluate(() => document.documentElement.scrollWidth > innerWidth)) throw new Error("A observação excedeu a largura da tela.");
        await page.goto(resultado);
        const destino = await page.locator("a.botao").getAttribute("href");
        const esperado = posicao===2 ? "/checkout/curso-teste/" : "/docs/laboratorio-crivo";
        if (destino !== esperado) throw new Error("Destino diferente da faixa.");
        await page.getByRole("button",{name:"Refazer o quiz"}).focus();
        await page.keyboard.press("Enter");
        await page.getByRole("heading",{name:"Laboratório Crivo",exact:true}).waitFor();
        if (await page.locator("input:checked").count() || await page.getByLabel("E-mail",{exact:true}).inputValue()) throw new Error("Refazer não limpou o formulário.");
        if (erros.length) throw new Error(erros.join("; "));
        provas.push({largura:tamanho.width,resultado:titulo,destino,teclado:true,retorno:true,refazer:true});
        await context.close();
      }
    }
    const semScripts = await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:844}});
    const pagina = await semScripts.newPage();
    await pagina.goto(`${base}/laboratorio-crivo/`);
    if (await pagina.locator("fieldset").count() !== 4) throw new Error("Sem scripts não mostrou o formulário completo.");
    for (const pergunta of await pagina.locator("fieldset[data-pergunta]:not([data-pergunta=lead])").all()) await pergunta.locator("input[type=radio]").first().check();
    await pagina.getByLabel("E-mail",{exact:true}).fill("laboratorio.crivo@exemplo.test");
    await pagina.getByRole("button",{name:"Ver resultado"}).click();
    await pagina.getByRole("heading",{name:"Escolha um projeto para começar",exact:true}).waitFor();
    await semScripts.close();
    provas.push({largura:390,semJavaScript:true,resultado:"Escolha um projeto para começar"});
    console.log(JSON.stringify(provas));
  } finally { await browser.close(); }
}
main().catch(erro => { console.error(erro); process.exitCode=1; });
