let chromium;
const requisicoesDeTelemetriaConsumidas = new WeakSet();
const requisicoesComResposta = new WeakSet();
try {
  ({ chromium } = require("playwright"));
} catch (erro) {
  throw new Error("Playwright não está instalado; execute npm install --no-save --no-package-lock playwright em services/quiz.");
}

async function esperarTelemetria(page, endpoint, tipo) {
  const resposta = await page.waitForResponse(item => {
    const request = item.request();
    if (item.url() !== endpoint || request.method() !== "POST") return false;
    if (requisicoesDeTelemetriaConsumidas.has(request)) return false;
    let dados;
    try {
      dados = request.postDataJSON();
    } catch {
      return false;
    }
    if (dados.event_type !== tipo) return false;
    requisicoesDeTelemetriaConsumidas.add(request);
    return true;
  }, { timeout: 10000 });
  if (resposta.status() !== 204) throw new Error(`Telemetria ${tipo} respondeu HTTP ${resposta.status()}.`);
}

async function main() {
  const base = new URL(process.argv[2]);
  const host = process.argv[3];
  if (!base.port || !host) throw new Error("Uso: node quiz_browser.js <live-server-url> <host-do-site>");
  let browser;
  try {
    browser = await chromium.launch();
  } catch (erro) {
    throw new Error(`Não consegui abrir o Chromium do Playwright: ${erro.message}`);
  }
  const erros = [];
  try {
    const page = await browser.newPage();
    const endereco = `${base.protocol}//${host}:${base.port}/crivo-e2e/`;
    const endpointTelemetria = new URL("/telemetry/", base).href;
    let enviandoValidacaoEsperada = false;
    let resposta422Esperada = false;
    let erro422DuranteValidacao = false;
    page.on("pageerror", erro => erros.push(`página: ${erro.message}`));
    page.on("console", mensagem => {
      if (mensagem.type() !== "error") return;
      if (enviandoValidacaoEsperada && mensagem.text().includes("422 (Unprocessable Entity)")) {
        erro422DuranteValidacao = true;
        return;
      }
      if (resposta422Esperada && mensagem.text().includes("422 (Unprocessable Entity)")) {
        resposta422Esperada = false;
        return;
      }
      erros.push(`console: ${mensagem.text()}`);
    });
    page.on("response", resposta => {
      requisicoesComResposta.add(resposta.request());
      if (resposta.status() < 400) return;
      const corpo = new URLSearchParams(resposta.request().postData() || "");
      const validacaoEsperada =
        enviandoValidacaoEsperada &&
        resposta.status() === 422 &&
        resposta.url() === endereco &&
        resposta.request().isNavigationRequest() &&
        resposta.request().method() === "POST" &&
        corpo.get("email") === "endereco-invalido";
      if (validacaoEsperada) {
        resposta422Esperada = !erro422DuranteValidacao;
        if (resposta422Esperada) setTimeout(() => { resposta422Esperada = false; }, 1000);
        return;
      }
      erros.push(`HTTP ${resposta.status()}: ${resposta.url()}`);
    });
    page.on("requestfailed", request => {
      if (requisicoesComResposta.has(request)) return;
      const falha = request.failure();
      const detalhe = typeof falha === "string" ? falha : falha?.errorText || JSON.stringify(falha);
      erros.push(`rede: ${request.method()} ${request.url()}: ${detalhe || "falha sem detalhe"}`);
    });
    await page.route("**/favicon.ico", rota => rota.fulfill({ status: 204, body: "" }));
    const telemetriaInicial = [
      esperarTelemetria(page, endpointTelemetria, "view_quiz"),
      esperarTelemetria(page, endpointTelemetria, "view_question"),
    ];
    const carregamento = await page.goto(endereco, { waitUntil: "networkidle" });
    if (!carregamento || carregamento.status() !== 200) throw new Error("O formulário não abriu com HTTP 200.");
    await Promise.all(telemetriaInicial);
    if (await page.locator("h1").innerText() !== "Crivo E2E") throw new Error("O título do quiz não apareceu.");

    const primeiro = page.locator("fieldset.passo.ativo");
    if (!(await primeiro.innerText()).includes("O que você quer aprender?")) throw new Error("A primeira pergunta não abriu.");
    await page.getByRole("button", { name: "Continuar" }).click();
    if (!(await primeiro.locator("[data-validacao]").isVisible())) throw new Error("Faltou orientação para a resposta obrigatória.");
    const cliquePrimeira = esperarTelemetria(page, endpointTelemetria, "click_option");
    await primeiro.locator('input[type="radio"]').nth(1).check();
    await cliquePrimeira;
    const proximaPergunta = esperarTelemetria(page, endpointTelemetria, "view_question");
    await page.getByRole("button", { name: "Continuar" }).click();
    await proximaPergunta;

    let ativo = page.locator("fieldset.passo.ativo");
    if (!(await ativo.innerText()).includes("Qual é seu próximo passo?")) throw new Error("A segunda pergunta não abriu.");
    const focoNaPergunta = await page.evaluate(() => {
      const campo = document.activeElement;
      return campo?.type === "radio" && Boolean(campo.closest("fieldset.passo.ativo"));
    });
    if (!focoNaPergunta) throw new Error("O foco não acompanhou a pergunta nova.");
    const cliqueSegunda = esperarTelemetria(page, endpointTelemetria, "click_option");
    await ativo.locator('input[type="radio"]').nth(1).check();
    await cliqueSegunda;
    await page.getByRole("button", { name: "Continuar" }).click();
    ativo = page.locator("fieldset.passo.ativo");
    if (!(await ativo.innerText()).includes("E-mail")) throw new Error("A etapa do e-mail não abriu.");
    if (await page.evaluate(() => document.activeElement?.getAttribute("name")) !== "email") throw new Error("O foco não acompanhou a etapa do e-mail.");

    const email = page.getByLabel("E-mail");
    await email.fill("endereco-invalido");
    await page.getByRole("button", { name: "Ver resultado" }).click();
    const validacaoNativa = await email.evaluate(campo => ({
      formatoInvalido: campo.validity.typeMismatch,
      orientacao: campo.validationMessage,
    }));
    if (!validacaoNativa.formatoInvalido || !validacaoNativa.orientacao) throw new Error("O navegador não orientou sobre o e-mail inválido.");

    const respostaInvalidaPromise = page.waitForResponse(resposta => {
      const corpo = new URLSearchParams(resposta.request().postData() || "");
      return resposta.url() === endereco &&
        resposta.request().isNavigationRequest() &&
        resposta.request().method() === "POST" &&
        corpo.get("email") === "endereco-invalido";
    }
    );
    const telemetriaAposErro = esperarTelemetria(page, endpointTelemetria, "view_quiz");
    erro422DuranteValidacao = false;
    enviandoValidacaoEsperada = true;
    await page.locator("form").evaluate(form => {
      form.noValidate = true;
      form.requestSubmit();
    });
    const respostaInvalida = await respostaInvalidaPromise;
    enviandoValidacaoEsperada = false;
    if (respostaInvalida.status() !== 422) throw new Error(`E-mail inválido não foi recusado: HTTP ${respostaInvalida.status()}.`);
    await page.getByText("Informe um e-mail válido para continuar.", { exact: true }).waitFor({ state: "visible" });
    await telemetriaAposErro;
    ativo = page.locator("fieldset.passo.ativo");
    if (!(await ativo.innerText()).includes("E-mail")) throw new Error("A etapa do e-mail não voltou ativa após a validação.");
    if (await page.locator('fieldset[data-pergunta]:not([data-pergunta="lead"])').nth(0).locator('input[type="radio"]:checked').count() !== 1) throw new Error("A primeira resposta se perdeu após a validação.");
    if (await page.locator('fieldset[data-pergunta]:not([data-pergunta="lead"])').nth(1).locator('input[type="radio"]:checked').count() !== 1) throw new Error("A segunda resposta se perdeu após a validação.");
    if ((await page.getByLabel("E-mail").inputValue()) !== "endereco-invalido") throw new Error("O e-mail inválido não foi preservado para correção.");
    if (await page.evaluate(() => document.activeElement?.getAttribute("name")) !== "email") throw new Error("O foco não voltou ao campo de e-mail inválido.");
    // Voltar pelo histórico restaura a página da memória, com o botão como o
    // envio o deixou. O Playwright desliga essa memória do Chromium, então o
    // evento que ela emite é disparado aqui, depois de um envio simulado.
    const restaurada = await page.locator("form").evaluate(form => {
      form.dispatchEvent(new SubmitEvent("submit", { cancelable: true }));
      const botao = form.querySelector("button.enviar");
      const travadoNoEnvio = botao.disabled;
      window.dispatchEvent(new PageTransitionEvent("pageshow", { persisted: true }));
      return { travadoNoEnvio, desligado: botao.disabled, rotulo: botao.textContent };
    });
    if (!restaurada.travadoNoEnvio || restaurada.desligado || restaurada.rotulo !== "Ver resultado") throw new Error(`A página restaurada do histórico não voltou a aceitar o envio: ${JSON.stringify(restaurada)}.`);
    await page.getByLabel("E-mail").fill("e2e@exemplo.test");
    // O envio fica retido no roteador até o estado de carregamento ser lido:
    // numa rede rápida ele sumiria antes de qualquer conferência.
    let liberarEnvio;
    const envioRetido = new Promise(resolve => { liberarEnvio = resolve; });
    await page.route(endereco, async rota => {
      if (rota.request().method() === "POST") await envioRetido;
      await rota.continue();
    });
    const navegacaoResultado = page.waitForNavigation({ waitUntil: "networkidle" });
    // O clique do Playwright espera a navegação começar, e ela está retida.
    // O clique do próprio botão dispara o mesmo envio, e o evento submit roda
    // dentro dele: o estado lido logo depois é o que a pessoa vê esperando.
    const carregando = await page.getByRole("button", { name: "Ver resultado" }).evaluate(botao => {
      botao.click();
      return { desligado: botao.disabled, rotulo: botao.textContent };
    });
    liberarEnvio();
    await navegacaoResultado;
    await page.unroute(endereco);
    if (!carregando.desligado || carregando.rotulo !== "Calculando seu resultado…") throw new Error(`O envio não mostrou carregamento: ${JSON.stringify(carregando)}.`);

    const resultado = await page.locator("main h1").innerText();
    const botaoResultado = page.locator("a.botao");
    if (!(await botaoResultado.isVisible())) throw new Error("O botão do próximo passo não está visível.");
    const proximoPasso = await botaoResultado.getAttribute("href");
    const rotuloProximoPasso = await botaoResultado.innerText();
    if (resultado !== "Pronto para avançar") throw new Error(`Resultado inesperado: ${resultado}.`);
    if (proximoPasso !== "/teste/continuidade/") throw new Error(`Destino inesperado no resultado: ${proximoPasso}.`);
    if (rotuloProximoPasso !== "Próximo passo") throw new Error(`Rótulo inesperado no botão: ${rotuloProximoPasso}.`);
    const urlResultado = page.url();

    const volta = await page.goto(endereco, { waitUntil: "networkidle" });
    if (!volta || volta.status() !== 200) throw new Error("A volta ao endereço do quiz não abriu com HTTP 200.");
    if (await page.locator("main h1").innerText() !== resultado) throw new Error("Quem já concluiu não voltou ao próprio resultado.");
    if (erros.length) throw new Error(`Erros inesperados no navegador ou servidor: ${erros.join(" | ")}`);
    console.log(JSON.stringify({ url: urlResultado, retomada: page.url(), resultado, proximo_passo: proximoPasso, rotulo_proximo_passo: rotuloProximoPasso }));
  } finally {
    await browser.close();
  }
}

main().catch(erro => {
  console.error(erro.stack || erro.message);
  process.exitCode = 1;
});
