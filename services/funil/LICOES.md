# LICOES — services/funil

Específico da célula. Transversal vai em `ARMADILHAS.md` na raiz.

## `{% load static %}` antes de `{% extends %}` quebra o parse

**Sintoma:** `TemplateSyntaxError: <ExtendsNode: extends "base_mobile.html"> must
be the first tag in the template.`
**Causa:** `{% extends %}` precisa ser literalmente a primeira tag do arquivo —
até `{% load %}` antes dela conta como "não-texto" e derruba a regra.
**Solução:** `{% extends %}` na linha 1, `{% load static %}` (e comentários
`<!-- -->`, que são texto puro e não contam) depois.
**Origem:** despacho funil/vitrine — `templates/funil/landing.html`.

## Autoescape do Django transforma `&` em `&amp;` dentro de `href`

**Sintoma:** teste que monta a URL esperada com `&` cru falha comparando
contra o HTML renderizado.
**Causa:** o autoescape do template protege atributos HTML — `&` vira
`&amp;`. É o comportamento correto (o browser decodifica normalmente); o erro
estava no teste, não na view.
**Solução:** ao comparar contra `resp.content` bruto, escreva a asserção
já esperando `&amp;` entre os parâmetros da query string.
**Origem:** despacho funil/vitrine — `tests/test_landing.py`.

## O middleware CONV-SITE roda mesmo quando a view vai devolver 422

**Sintoma:** teste que espera "nenhuma chamada de rede" numa rota de erro (ex.:
e-mail ausente no POST /leads) falha, porque o catálogo FOI chamado.
**Causa:** [INV-P11]/CONV-SITE resolve Host→Site em TODA requisição, antes de
qualquer validação da view — igual ao que ARMADILHAS.md §4.6 já registrou para
checkout (middleware roda antes da auth do django-ninja; aqui é antes da
validação do form). A chamada ao catálogo é inevitável mesmo em caminhos de
erro do domínio da própria célula.
**Solução:** teste de "efeito colateral que não deveria acontecer" precisa
filtrar por endpoint específico (`"/leads" in str(chamada.request.url)`), não
assumir "nenhuma chamada de rede" — a resolução de site sempre bate.
**Origem:** despacho funil/vitrine — `tests/test_lead_capture.py`.

## Decisão: teste-guarda de mobile-first é local à célula, não [INV-Pxx]

O despacho pediu `test_mobile_first_contract` como teste-guarda, mas
"mobile-first por contrato" aqui é uma exigência DESTA célula (a primeira a
usar a receita R6 na prática), não um invariante de dinheiro/multissítio como
os listados em `INVARIANTES.md`. Não criei entrada `[INV-Pxx]` para isso —
o guarda vive em `tests/test_mobile_first_contract.py` e verifica, no HTML
servido (sem precisar de browser real): viewport `width=device-width` único e
sem largura fixa, e o container raiz (`.wrap`) usando `max-width` em `rem`
(fluido), nunca `width` em `px`. Se uma segunda célula reusar `base_mobile.html`
como padrão comum, esse é o gatilho para promover isto a invariante de
plataforma.

## `templates/base_mobile.html` é de propriedade DESTA célula, não compartilhado

Cada célula pública (funil, quiz, checkout, alunos) tem seu próprio
`base_mobile.html`/base de página — não existe um template compartilhado entre
células (Lei 7 do Caminho Dourado: "cada célula tem o seu — copie o padrão,
não o arquivo"). `services/checkout` já roda R6 sem base compartilhada
(cada página HTML é standalone); `services/funil` foi a primeira a introduzir
um `base_mobile.html` local, mas ele não deve ser extraído para fora desta
célula sem decisão explícita do mantenedor.

## A matriz HTTP do i18n (D1) devolve 404 ao POST /leads de site REGISTRADO — pendência real da fase 2

**Sintoma:** com um site registrado em `sites_i18n.yaml`, o formulário da
landing quebraria: a ilha Alpine posta em `/leads` (caminho nu), e a matriz do
PLANO-I18N D1 manda caminho nu não-GET para **404** (redirect converteria POST
em GET e descartaria o corpo).
**Causa:** `/leads` não está em `CAMINHOS_SEM_SITE` nem na lista de rotas de
máquina do D6 (`/api/**`, `/webhooks/**`, `/static/**`, `/healthz`) — é
caminho nu como qualquer outro. Comportamento INTENCIONAL da fase 1 (testado
em `test_post_leads_em_site_registrado_e_404_pela_matriz`): nenhum site real
está registrado, então nada quebra em produção.
**Solução (fase 2):** quando registrar o meshcraft, decidir o canal de POST —
prefixar o destino do form (`/{idioma}/leads`, que o resolver decapa e o
urlconf resolve), ou promover `/leads` a rota de máquina. Sem essa decisão, o
formulário do site registrado nasce morto.
**Origem:** despacho funil/i18n-fundacao.

## O resolver decapa o prefixo em `request.path_info`; `request.path` fica intacto

O middleware reescreve `request.path_info` (`/en/cadastro` → `/cadastro`)
ANTES da resolução de URL — o urlconf da célula continua sem nenhum prefixo, e
toda página futura ganha os idiomas de graça. `request.path` segue completo
(`/en/cadastro`), e é dele que sai o canonical. Duas consequências:
1. `{% url %}`/links relativos gerados por view NÃO levam prefixo de idioma —
   a fase 2 precisa do helper de URL com idioma antes de linkar entre páginas
   de site registrado (pendência já registrada no D6 do plano).
2. `/en` sem barra → 302 `/en/` (decisão desta célula, não estava na matriz:
   evita duas URLs servindo o mesmo conteúdo).
**Origem:** despacho funil/i18n-fundacao — `apps/core/middleware.py`.

## Regressão byte-idêntica do base_mobile: como o template muda sem mudar um byte

`test_regressao_site_nao_registrado_landing_byte_identica` compara a landing
de site NÃO registrado com o HTML capturado ANTES desta fase (constante
`HTML_DE_HOJE` embutida no teste). Para o template crescer sem quebrar isso,
todas as tags `{% if %}`/`{% comment %}` novas colam no fim da linha anterior
(ver ARMADILHAS §4.14 — a lição vale para qualquer célula). Se um despacho
futuro mudar a landing DE PROPÓSITO: recapture o HTML renderizado (site de
teste, sem i18n) e atualize a constante — nunca afrouxe a comparação para
`in`/regex, que é o que deixaria o vazamento de i18n passar.
**Origem:** despacho funil/i18n-fundacao — `tests/test_i18n_http.py`.

## `/checkout/<slug>/` tem barra final — confirmado na branch paralela

O link do botão de compra usa `f"/checkout/{slug}/"` (com `/` no final) porque
é o formato real de `path("checkout/<slug:offer_slug>/", ...)` que a célula
checkout está implementando em paralelo (branch `agent/checkout/paginas`,
worktree `wt-checkout-paginas`, commit `d0ae88d`). Se essa rota mudar de
formato, o link daqui quebra silenciosamente — nenhum teste desta célula pode
pegar isso, porque checkout não roda aqui (R2: só o contrato). Vale a pena um
smoke cross-célula manual depois que os dois PRs (funil e checkout/paginas)
estiverem mergeados.
