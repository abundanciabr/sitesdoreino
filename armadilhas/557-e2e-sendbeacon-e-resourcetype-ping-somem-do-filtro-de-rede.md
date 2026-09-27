---
schema_version: 2
armadilha: 557
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: medio
gatilho:
  - e2e/ensaio_experimento.js
  - e2e/painel_no_navegador.js
sinal:
  - "resourceType\\(\\).{0,20}(xhr|fetch|other)"
guarda:
  tipo: nenhum
  motivo: "e um padrao de leitura de codigo em roteiros de navegador (Playwright/Puppeteer); nenhum portao local mede se um filtro de resourceType esqueceu ping ou se um listener de captura chama stopPropagation"
licao: "sendBeacon chega ao Playwright com resourceType() === ping, fora do trio xhr/fetch/other. Um listener de clique em fase de captura que chama stopPropagation cala listener de telemetria da propria pagina em fase de bolha; preventDefault sozinho ja cancela a navegacao."
---

# 557: em e2e, `sendBeacon` some do filtro de `resourceType` e `stopPropagation` cala a telemetria da página

**Data:** 27/09/2026 · **Onde:** `e2e/ensaio_experimento.js` · **Custo
evitado:** ensaio de telemetria fica verde ou vermelho por engano, achando
que o evento de negócio não disparou quando na verdade o roteiro é que não
o via.

## Sintoma

Um roteiro Playwright que observa `requestfinished` e filtra por
`req.resourceType()` só via `"xhr"`, `"fetch"` e `"other"`; chamadas de
`navigator.sendBeacon(...)` (usadas por `telemetria.js` para o evento
`cta-clicado`) nunca apareciam na lista de chamadas capturadas, mesmo
disparando de verdade no navegador. Em paralelo, um `document.addEventListener("click", fn, true)`
instalado pelo próprio roteiro (fase de captura, para impedir a navegação
antes que ela aconteça) chamava `evento.stopPropagation()`; isso impedia o
listener de clique de `telemetria.js` (fase de bolha, no mesmo `document`)
de sequer rodar, então o beacon `cta-clicado` nunca era enviado pela
página.

## Causa

O Chromium reporta requisições feitas por `navigator.sendBeacon()` com
`resourceType() === "ping"`, um valor fora do trio comum `xhr/fetch/other`
que a maioria dos filtros de rede considera suficiente. Separadamente,
`stopPropagation()` interrompe a propagação do evento de clique para
qualquer outro listener do mesmo tipo no mesmo alvo, incluindo os da
própria página sob teste; `preventDefault()` já é suficiente para cancelar
a navegação de um link, porque roda na mesma fase de captura, antes do
despacho decidir o destino final do clique. `stopPropagation()` ali não
adiciona proteção nenhuma, só cala listeners legítimos da página.

## Solução

Em filtro de rede por `resourceType()` em roteiros de e2e/Playwright,
inclua `"ping"` ao lado de `"xhr"`, `"fetch"` e `"other"` sempre que o
evento observado puder ser um `sendBeacon`. Em listener de clique instalado
para interceptar navegação, use só `preventDefault()`; não chame
`stopPropagation()` a menos que exista um motivo específico e documentado
para silenciar outros listeners do mesmo evento, porque isso apaga
telemetria e outros efeitos colaterais legítimos da página sob teste.

## Origem

PR #2296 (TAR-921), `e2e/ensaio_experimento.js`
(`observarTelemetria`, `instalarCapturaDeClique`).
