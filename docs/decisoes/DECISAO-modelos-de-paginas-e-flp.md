# DECISÃO - modelos de páginas e publicação da FLP

**Data:** 24/09/2026 · **Quem decidiu:** contrato técnico da Fase 0 · **Estado:** valendo para as próximas frentes

## O pedido

Implementar a gestão de páginas em `/admin/modelos-de-paginas/` e publicar a
Fórmula de Lançamento Pago em `https://meshcraft.top/flp-0`.

O problema real não é uma tela nova no admin. É fazer uma página clonada sair no
site público com versão, dono, caminho, segurança, auditoria e prova de
publicação, sem criar uma segunda célula de páginas nem uma regra de Traefik por
página.

## Inventário medido

### Admin

Já existe a prévia privada da FLP em:

| Caminho | O que faz |
|---|---|
| `/admin/modelos-de-paginas/flp-0` | moldura autenticada com iframe sandbox |
| `/admin/modelos-de-paginas/flp-0/conteudo` | conteúdo HTML embutido do pacote `flp-0.zip.b64` |

`services/admin/apps/core/modelo_flp.py` lê o pacote base64, incorpora recursos
como `data:` e serve o conteúdo em origem opaca, sem `allow-same-origin`. O CSP
permite script e formulário dentro do sandbox, `connect-src` para CrazyLeads e
`form-action` para CrazyLeads e Hotmart. Os testes atuais cobrem porta
administrativa, prefixo `/admin`, CSP, isolamento e recusa de POST.

Também já existe o editor `/admin/paginas/`, mas ele é a tela da página de
oferta canônica. Ele grava o slug fixo `oferta` via `getPageDraft`,
`putPageDraft` e `publishPage`, com auditoria em cada gravação e publicação.

### Catálogo

O catálogo já tem o núcleo certo:

| Peça | Estado |
|---|---|
| `Page` | identidade estável por `site` e `slug`, com unicidade por site |
| `PageDraft` | rascunho mutável, um por página |
| `PageVersion` | versão publicada imutável |
| contrato | `getPage`, `getPageDraft`, `putPageDraft`, `publishPage` |

O que falta é a forma de dizer qual modelo renderiza a página. Hoje o contrato
de `PaginaPublicada` devolve `slug`, `version`, `offer_slug` e `secoes`; isso
serve para `/oferta`, mas não diz ao funil que `/flp-0` deve usar o modelo FLP.

### Funil

O funil já renderiza uma página pública vinda do catálogo em `/oferta`. Ele lê o
slug fixo `oferta`, trata 404 como página inexistente, trata catálogo mudo como
503 com `Retry-After`, mede `funil.pagina-vista` com `pagina_slug` e
`pagina_version`, e monta o checkout com barra final.

O funil ainda não tem rota `/flp-0`. O urlconf atual declara rotas explícitas e
deixa a raiz como catch-all. A célula também tem o middleware `BarraNoFinal`:
GET/HEAD com barra extra em rota sem barra redireciona para a forma nua; POST
com barra não redireciona.

### Clone original da FLP

O clone local em `C:\Users\davia\paginas\fl-gpt` preserva estrutura, imagens,
fontes, FAQ e formulário. A validação local mediu 65 recursos com HTTP 200,
desktop e celular sem transbordamento horizontal, botões, formulário, DDI, FAQ
e ausência de script HTTP externo depois da correção. Inscrição real e pagamento
não foram executados. O webhook externo original da CrazyLeads permanece como
destino do formulário.

## Decisão

A página pública da FLP pertence ao fluxo canônico já existente:

1. O catálogo continua sendo dono de identidade, rascunho e publicação.
2. O admin opera a página; não guarda cópia do fato publicado.
3. O funil renderiza o que está publicado no catálogo.
4. A célula `pages` não entra neste trabalho, porque ela é a Prancheta e a
vitrine do aluno.
5. Traefik não muda por página. `/flp-0` cai no catch-all do funil, como
qualquer página pública do site.

A menor entrega inteira é:

1. Registrar no catálogo que uma página usa o modelo `flp-0`.
2. Expor esse modelo na resposta publicada.
3. Criar `/admin/modelos-de-paginas/` como tela de operação da FLP, com lista,
prévia, gravação e publicação do slug `flp-0`.
4. Renderizar `/flp-0` no funil somente quando a versão publicada existir e
declarar o modelo `flp-0`.
5. Medir a publicação pela borda pública em `https://meshcraft.top/flp-0`.

## Contrato e dados necessários

Há uma mudança real de contrato: `PaginaPublicada` precisa informar o modelo da
página. O campo novo é aditivo e opcional para compatibilidade:

```yaml
model_slug: string
```

Regra:

- ausente ou vazio significa o renderizador estruturado atual de `/oferta`;
- `flp-0` significa o renderizador do modelo Fórmula de Lançamento Pago;
- valor desconhecido no funil vira 503 com mensagem de modelo indisponível, não
  uma página em branco.

No banco do catálogo, o dado correspondente fica na identidade da página e viaja
para cada versão publicada. O rascunho pode mudar texto e configuração, mas não
troca de modelo por acidente ao salvar. Para a primeira entrega, o slug
`flp-0` nasce com `model_slug = "flp-0"`.

Não é necessário criar `public_path` agora. O caminho público desta fase é o
slug com barra inicial: `flp-0` vira `/flp-0`. Quando houver página com caminho
em subpasta, isso será outro rito, porque muda a regra de resolução pública.

## Regra de caminhos públicos

`/flp-0` é o endereço canônico. A forma com barra final é entrada tolerada para
GET/HEAD e deve redirecionar para `/flp-0`. POST em `/flp-0/` não redireciona.

O slug público:

- usa apenas `a-z`, `0-9` e hífen;
- não tem barra, ponto, sublinhado nem acento;
- não tem forma de idioma;
- não pode colidir com rota já declarada no funil ou com prefixo do Traefik.

Caminhos reservados nesta fase:

`api`, `quiz`, `checkout`, `alunos`, `forms`, `entrar`, `admin`, `mapa-ia`,
`docs`, `midia`, `forum`, `conquistas`, `cursos`, `aulas`, `pages`, `estudio`,
`encomendas`, `healthz`, `sitemap.xml`, `manifest.webmanifest`, `sw.js`,
`static`, `leads`, `avisos`, `notificacoes`, `cadastro`, `oferta`, `ver-como`,
`login`, `google0e78b54775677e95.html`, e qualquer código de idioma declarado
para o site.

## Operação dos robôs

O robô do catálogo faz o contrato e o dado. Ele não toca admin nem funil no
mesmo PR se o contrato congelado mudar.

O robô do admin cria a tela de operação, usa apenas o contrato do catálogo, gera
auditoria e mantém a prévia privada específica da FLP. Ele não escreve no banco
do catálogo e não publica por arquivo local.

O robô do funil cria a rota pública `/flp-0`, consome `getPage`, confere
`model_slug`, preserva UTM no formulário quando aplicável, mantém fail-open de
renderização para partes externas recuperáveis e fail-closed para ausência de
publicação.

O robô de integração mede a borda pública depois do deploy. PR verde não prova
publicação em `meshcraft.top/flp-0`.

## Próximas frentes

As frentes podem ser paralelas somente depois do PR de contrato/dado do catálogo
estar aberto com o schema exato. Antes disso, admin e funil poderiam implementar
duas leituras diferentes de `modelo`, que é a colisão que esta Fase 0 existe
para impedir.

### Frente 1 - catálogo, contrato e dado

**Objetivo:** adicionar `model_slug` à identidade e à versão publicada da página,
exportar o campo no contrato e semear a página `flp-0`.

**Branch/worktree:** `agent/catalogo/modelos-de-paginas-contrato` em
`wt-catalogo-modelos-de-paginas-contrato`.

**Arquivos-alvo:** `contracts/catalogo.openapi.yaml`,
`services/catalogo/apps/paginas/models.py`,
`services/catalogo/apps/paginas/api.py`,
`services/catalogo/apps/paginas/migrations/`,
`services/catalogo/tests/test_paginas_pela_porta.py`,
`services/catalogo/tests/test_salvar_cria_a_pagina.py`.

**Somente leitura:** `services/admin/**`, `services/funil/**`,
`infra/traefik/dynamic/plataforma.yml`.

**Dependências:** rito de contrato, porque `contracts/catalogo.openapi.yaml` é
congelado.

**Provas:** reconstruir o OpenAPI a partir do export, provar que o congelado só
cresceu por adição, testar `getPage` com e sem `model_slug`, testar que
publicação preserva o modelo na versão, e testar que dois sites podem ter
`flp-0` distintos.

**Riscos e armadilhas:** serializador do contrato congelado, concorrência com
outro rito do catálogo, e falso-verde de publicar versão sem modelo.

### Frente 2 - admin, tela de modelos de páginas

**Objetivo:** entregar `/admin/modelos-de-paginas/` com lista da FLP, prévia,
estado publicado, botões de salvar/publicar e mensagens de erro que expliquem o
que aconteceu e o que fazer.

**Branch/worktree:** `agent/admin/modelos-de-paginas` em
`wt-admin-modelos-de-paginas`.

**Arquivos-alvo:** `services/admin/apps/core/modelo_flp.py`,
`services/admin/apps/core/templates/admin/modelo_flp.html`,
`services/admin/apps/core/templates/admin/modelos_de_paginas.html`,
`services/admin/config/urls.py`, `services/admin/tests/test_modelo_flp.py`,
`painel/mapa-do-site.json`.

**Somente leitura:** `services/catalogo/**`, `services/funil/**`,
`contracts/catalogo.openapi.yaml`.

**Dependências:** contrato da Frente 1 ou mock fiel dele.

**Provas:** porta admin fail-closed, prefixo `/admin` preservado, lista mostra
vazio/erro/carregando/primeiro uso, publicação audita sucesso e recusa, e a
prévia continua sandbox sem `allow-same-origin`.

**Riscos e armadilhas:** admin não escreve no banco do catálogo; CSP com iframe
precisa continuar `frame-ancestors 'self'`; rota nova exige mapa do site.

### Frente 3 - funil, rota pública `/flp-0`

**Objetivo:** servir a FLP publicada em `/flp-0` pelo funil, usando o catálogo
como fonte de publicação.

**Branch/worktree:** `agent/funil/flp-0-publica` em
`wt-funil-flp-0-publica`.

**Arquivos-alvo:** `services/funil/config/urls.py`,
`services/funil/apps/core/views.py`, `services/funil/apps/core/clients.py`,
`services/funil/templates/funil/`, `services/funil/tests/test_modelo_flp.py`,
`services/funil/tests/test_barra_no_final.py`, `painel/mapa-do-site.json`.

**Somente leitura:** `services/admin/**`, `services/catalogo/**`,
`contracts/catalogo.openapi.yaml`, `infra/traefik/dynamic/plataforma.yml`.

**Dependências:** contrato da Frente 1; artefato FLP definido como recurso do
funil ou pacote comum versionado.

**Provas:** `/flp-0` 200 quando publicado, 404 quando não publicado, 503 quando
modelo é desconhecido ou catálogo mudo, `/flp-0/` redireciona em GET e não em
POST, formulário mantém destino permitido, e evento `funil.pagina-vista` leva
slug e versão.

**Riscos e armadilhas:** toda rota nova no funil passa pela matriz de idioma; o
primeiro segmento não pode ter forma de locale; `BarraNoFinal` não pode mexer
em POST; página pública precisa ser medida de fora.

### Frente 4 - publicação e prova pública

**Objetivo:** publicar a versão `flp-0` e conferir a URL final em produção.

**Branch/worktree:** sem branch se for só operação após deploy; se precisar
semear dado por migração, `agent/catalogo/semear-flp-0`.

**Arquivos-alvo:** fila ou migração de semeadura mínima, conforme o resultado
da Frente 1.

**Somente leitura:** código de admin, funil e contrato já integrados.

**Dependências:** Frentes 1, 2 e 3 integradas e deployadas.

**Provas:** `Invoke-WebRequest https://meshcraft.top/flp-0` com HTTP 200,
HTML com a página da FLP, recursos carregados sem erro observável, mobile sem
transbordamento, e registro no livro com URL e data.

**Riscos e armadilhas:** PR integrado não é publicação; CrazyLeads e Hotmart são
serviços externos e não devem receber inscrição ou compra real na validação.

## O que fica fora desta entrega

Editor visual, checkout próprio, captura própria, cobrança própria, Traefik por
página, múltiplos caminhos públicos simultâneos, mexer no clone original, usar
a célula `pages`, e publicar teste na página comercial real.

## Provas da Fase 0

A abertura de sessão com baseline de serviço parou antes da declaração porque o
instrumento local chamou `make.CMD -C ...` e recebeu `ERROR: alvo desconhecido:
-C`. A bancada foi retomada em modo `--sem-container`, adequado a esta fase
documental, e por isso não há baseline de serviço.

As leituras desta decisão vieram de `origin/main:<caminho>` para os arquivos
de produto, porque a abertura avisou que a árvore local estava atrasada em 81
entregas. O inventário também leu `LEIA-ME.md` e `VALIDACAO.md` do clone local
da FLP.
