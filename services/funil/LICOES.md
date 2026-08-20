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

## `/checkout/<slug>/` tem barra final — confirmado na branch paralela

O link do botão de compra usa `f"/checkout/{slug}/"` (com `/` no final) porque
é o formato real de `path("checkout/<slug:offer_slug>/", ...)` que a célula
checkout está implementando em paralelo (branch `agent/checkout/paginas`,
worktree `wt-checkout-paginas`, commit `d0ae88d`). Se essa rota mudar de
formato, o link daqui quebra silenciosamente — nenhum teste desta célula pode
pegar isso, porque checkout não roda aqui (R2: só o contrato). Vale a pena um
smoke cross-célula manual depois que os dois PRs (funil e checkout/paginas)
estiverem mergeados.
