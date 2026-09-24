# DECISAO: modelos de paginas e FLP-0

> Sessao de arquitetura, 24/09/2026. Pedido: implementar gestao em
> `/admin/modelos-de-paginas/`, previa privada
> `/admin/modelos-de-paginas/flp-0` e publicacao publica `/flp-0` em
> `meshcraft.top`.

## 1. Decisao

`flp-0` sera uma pagina publica do `funil`, lida do `catalogo` pelo mesmo
mecanismo de paginas versionadas que hoje serve `/oferta`.

A copia fechada que ja existe em `/admin/modelos-de-paginas/flp-0` fica como
modelo privado e fonte de referencia visual. Ela nao vira pagina publica por
redirecionamento, iframe aberto ou Traefik novo.

Escolha: usar a casa ja pronta de `Page`, `PageDraft` e `PageVersion`.
Motivo: ela ja resolve site por Host, rascunho privado, publicacao imutavel,
versao para telemetria e 404 quando nada foi publicado.

## 2. Inventario medido

### Admin

Existe hoje:

- `/admin/modelos-de-paginas/flp-0`
- `/admin/modelos-de-paginas/flp-0/conteudo`
- `services/admin/apps/core/modelo_flp.py`
- `services/admin/apps/core/templates/admin/modelo_flp.html`
- `services/admin/apps/core/modelos/flp-0.zip.b64`
- `services/admin/tests/test_modelo_flp.py`

Comandos:

```powershell
rg "modelo_flp|modelos-de-paginas|flp-0" -n services\admin painel infra docs
```

Resultado relevante:

```text
services\admin\config\urls.py:173: path("modelos-de-paginas/flp-0", modelo_flp, name="modelo_flp")
services\admin\config\urls.py:175: "modelos-de-paginas/flp-0/conteudo"
services\admin\apps\core\modelo_flp.py:16: PACOTE = Path(__file__).with_name("modelos") / "flp-0.zip.b64"
services\admin\tests\test_modelo_flp.py:14: ROTAS = ["/modelos-de-paginas/flp-0", "/modelos-de-paginas/flp-0/conteudo"]
painel\mapa-do-site.json:46: "rota": "modelos-de-paginas/flp-0"
painel\registros\20260924-010-flp-publicacao-conferida.js:8: evidencia: "https://meshcraft.top/admin/modelos-de-paginas/flp-0; ..."
```

O pedido antigo que dizia que `modelo_flp.py`, template e teste nao existiam
esta desatualizado para esta revisao. Eles existem e ja foram conferidos por
registro de publicacao.

### Catalogo

Existe hoje:

- `Page`: identidade da pagina por `site` e `slug`.
- `PageDraft`: rascunho mutavel, um por pagina.
- `PageVersion`: versao publicada imutavel.
- Operacoes congeladas: `getPage`, `getPageDraft`, `putPageDraft` e
  `publishPage`.

Comando:

```powershell
rg "getPage|putPageDraft|publishPage|paginas" -n contracts\catalogo.openapi.yaml
```

Resultado relevante:

```text
164:  /sites/{site_id}/paginas/{slug}:
166:      operationId: getPage
192:  /sites/{site_id}/paginas/{slug}/rascunho:
194:      operationId: getPageDraft
217:      operationId: putPageDraft
246:  /sites/{site_id}/paginas/{slug}/publicar:
248:      operationId: publishPage
```

Falta para `flp-0`: o vocabulario atual e fechado para as onze secoes da
pagina de oferta. `flp-0` precisa de um `tipo` ou `template_slug` no dominio de
pagina, ou de uma decisao equivalente, antes de aceitar outro vocabulario sem
misturar formas diferentes no mesmo validador.

### Funil

Existe hoje:

- `/oferta`, renderizada de `CatalogoClient.obter_pagina(site_id, "oferta")`.
- Tratamento separado para pagina nao publicada, catalogo mudo e corpo fora do
  contrato.
- Telemetria por `pagina_slug` e `pagina_version`.

Comandos:

```powershell
rg "pagina_de_oferta|obter_pagina|SLUG_DA_PAGINA_DE_OFERTA" -n services\funil\apps\core
Get-Content services\funil\config\urls.py | Select-String "oferta"
```

Resultado relevante:

```text
services\funil\apps\core\views.py:162: SLUG_DA_PAGINA_DE_OFERTA = "oferta"
services\funil\apps\core\views.py:297: pagina = catalogo.obter_pagina(site["id"], SLUG_DA_PAGINA_DE_OFERTA)
services\funil\config\urls.py:52: path("oferta", pagina_de_oferta, name="pagina_de_oferta")
```

Falta para `flp-0`: rota publica `path("flp-0", ...)`, template ou renderizador
publico proprio, classificacao da rota como pagina localizavel quando couber,
entrada no mapa do site e testes do caminho triste.

### Traefik

Nao falta router para `/flp-0`. O catch-all `funil` ja serve caminhos publicos
que nenhum prefixo de celula captura.

Comando:

```powershell
rg "admin:|funil:|PathPrefix\(`/`\)|PathPrefix\(`/admin`\)" -n infra\traefik\dynamic\plataforma.yml
```

Resultado relevante:

```text
admin: Host(`meshcraft.top`) && PathPrefix(`/admin`) -> service admin
funil: PathPrefix(`/`) -> service funil
```

Falta de infra: nenhuma para o caminho publico. Acrescentar Traefik por pagina
criaria uma segunda fonte de roteamento e contraria o desenho multissitio.

### Clone original

Comandos:

```powershell
Get-Content -Raw C:\Users\davia\paginas\fl-gpt\LEIA-ME.md
Get-Content -Raw C:\Users\davia\paginas\fl-gpt\VALIDACAO.md
```

Resultado relevante:

- clone roda em `http://localhost:4173` com Node.js, sem instalar pacotes;
- recursos visuais locais preservados;
- CrazyLeads e Hotmart continuam externos;
- pixels externos e Google Tag Manager foram desativados;
- validacao local conferiu 65 recursos com HTTP 200, desktop e mobile;
- inscricao real e pagamento nao foram executados;
- erro React #418 herdado da origem foi observado e a tela se recuperou.

## 3. Fluxo canonico

1. A equipe abre `/admin/modelos-de-paginas/flp-0` para ver a referencia
   fechada, isolada em iframe sem `allow-same-origin`.
2. A equipe abre `/admin/modelos-de-paginas/` para gerir os modelos editaveis.
3. Salvar grava `PageDraft(site=meshcraft.top, slug="flp-0")` no `catalogo`.
4. Previa privada abre a versao de rascunho por uma rota administrativa, nunca
   pela rota publica.
5. Publicar chama `publishPage(site_id, "flp-0")` e cria `PageVersion`.
6. Visitante abre `https://meshcraft.top/flp-0`.
7. `funil` resolve Host para Site, chama `getPage(site_id, "flp-0")` e renderiza
   a versao publicada.
8. Evento de visita carrega `site_id`, `pagina_slug="flp-0"` e
   `pagina_version`, nunca a copy.

## 4. Regras de caminho

- Publico: `/flp-0`, sem barra final canonica.
- Privado: `/admin/modelos-de-paginas/flp-0`, mantendo o modelo fechado atual.
- Gestao: `/admin/modelos-de-paginas/`.
- Previa de rascunho: `/admin/modelos-de-paginas/flp-0/previa`.
- Conteudo interno do modelo fechado: `/admin/modelos-de-paginas/flp-0/conteudo`.

`/flp-0/` pode redirecionar para `/flp-0` por `APPEND_SLASH` ou recusar com 404,
mas nao deve servir uma segunda pagina. Uma pagina, um caminho publico.

## 5. Caminhos reservados

Reservados no admin:

- `/admin/modelos-de-paginas/novo`
- `/admin/modelos-de-paginas/criar`
- `/admin/modelos-de-paginas/<slug>`
- `/admin/modelos-de-paginas/<slug>/salvar`
- `/admin/modelos-de-paginas/<slug>/publicar`
- `/admin/modelos-de-paginas/<slug>/previa`
- `/admin/modelos-de-paginas/<slug>/conteudo`

Reservados no funil:

- `/flp-0`
- nenhum prefixo sob `/admin`;
- nenhum prefixo de maquina;
- nenhum primeiro segmento com forma de idioma.

Slug de pagina publica aceita somente `[a-z0-9-]+`. Nomes administrativos como
`novo`, `criar`, `salvar`, `publicar`, `previa` e `conteudo` sao reservados.

## 6. Operacoes dos robos

`catalogo`:

- manter site por Host como fronteira;
- estender paginas por adicao, preservando as operacoes atuais;
- se mudar contrato, fazer PR exclusivo de `contracts/` pelo RITOS §3;
- semear `flp-0` por comando idempotente ou migracao propria, sem INSERT manual.

`admin`:

- listar modelos, abrir modelo, salvar rascunho, publicar e abrir previa;
- auditar cada escrita;
- falha de catalogo mostra o que aconteceu e como tentar de novo;
- nao guardar copia do conteudo no banco da `admin`.

`funil`:

- renderizar apenas versao publicada;
- pagina nao publicada responde 404 com mensagem acionavel;
- catalogo mudo responde 503 com `Retry-After`;
- corpo fora do contrato nao vira 500;
- medicao falha aberta.

`infra`:

- nao criar router por pagina;
- usar catch-all do `funil`;
- so tocar Traefik se a propria lista de caminhos publicos provar colisao.

## 7. Mudancas necessarias

Contrato e dados:

- `catalogo` precisa distinguir a forma da pagina. O menor desenho e adicionar
  `tipo` opcional em `Page` e nos schemas de pagina, com valor inicial
  `"oferta"` para a pagina existente e `"flp"` para `flp-0`.
- Esse campo e aditivo, mas toca contrato congelado. Entra pelo RITOS §3 em PR
  proprio de `contracts/`.
- O vocabulario deixa de ser uma lista unica global e passa a ser escolhido por
  `tipo`.

Admin:

- criar `/admin/modelos-de-paginas/` como lista e editor de modelos;
- reaproveitar o cliente do catalogo, sem banco local;
- manter a rota fechada atual de `flp-0` como referencia visual.

Funil:

- criar renderizador publico para `flp-0`;
- reaproveitar `CatalogoClient.obter_pagina`;
- adicionar `flp-0` ao inventario de rotas e ao sitemap somente quando houver
  pagina publicada e decisao SEO.

Infra:

- nenhuma mudanca prevista.

## 8. Proximas frentes

As proximas frentes podem rodar em paralelo depois do PR de contrato. Antes
dele, `catalogo`, `admin` e `funil` colidem no significado de `Page.secoes`.

### Frente 1 - contrato de paginas tipadas

- Objetivo: acrescentar `tipo` opcional aos schemas de pagina do catalogo.
- Branch/worktree: `agent/contratos/paginas-tipadas`.
- Arquivos-alvo: `contracts/catalogo.openapi.yaml`.
- Somente leitura: `services/catalogo/apps/paginas/api.py`,
  `services/funil/apps/core/clients.py`, `services/admin/apps/core/clients.py`.
- Dependencias: nenhuma.
- Contratos: RITOS §3, PR exclusivo de contrato.
- Provas: freeze de contrato, aditivo sem remocao, consumidores atuais aceitam
  ausencia do campo.
- PR proprio: sim.
- Riscos: campo obrigatorio quebrar consumidores; schema exportado divergir.
- Armadilhas: campo opcional usa `default_factory`, nunca `default=`.

### Frente 2 - catalogo aceita vocabulario por tipo

- Objetivo: `Page.tipo`, vocabularios `oferta` e `flp`, seed de `flp-0`.
- Branch/worktree: `agent/catalogo/paginas-tipadas-flp`.
- Arquivos-alvo: `services/catalogo/apps/paginas/**`,
  `services/catalogo/tests/**`.
- Somente leitura: `contracts/catalogo.openapi.yaml`.
- Dependencias: Frente 1.
- Contratos: implementar exatamente o contrato aditivo.
- Provas: modelo/migration, normalizacao por tipo, versao publicada imutavel,
  seed idempotente e `getPage` de pagina inexistente continua 404.
- PR proprio: sim.
- Riscos: `oferta` mudar forma sem querer; seed apagar rascunho do mantenedor.
- Armadilhas: `update()` tambem valida; dado inicial usa R9.

### Frente 3 - admin de modelos de paginas

- Objetivo: lista, editor, salvar, publicar e previa privada de `flp-0`.
- Branch/worktree: `agent/admin/modelos-de-paginas`.
- Arquivos-alvo: `services/admin/apps/core/modelos_de_paginas.py`,
  templates, urls, testes e `painel/mapa-do-site.json`.
- Somente leitura: `services/admin/apps/core/modelo_flp.py`,
  `services/admin/apps/core/paginas.py`, contrato do catalogo.
- Dependencias: Frente 1 e API da Frente 2 disponivel em mock ou implementada.
- Contratos: cliente do catalogo so chama operacoes congeladas.
- Provas: porta fail-closed, sem catalogo preserva texto digitado, publica
  com auditoria, previa nao publica, modelo fechado atual continua isolado.
- PR proprio: sim.
- Riscos: duplicar conteudo no banco da admin; iframe vazar origem.
- Armadilhas: classes CSS novas conferidas contra `base.html`; CSP sem
  `allow-same-origin`.

### Frente 4 - funil publica `/flp-0`

- Objetivo: rota publica `/flp-0` renderizada de `getPage(site_id, "flp-0")`.
- Branch/worktree: `agent/funil/flp-0-publico`.
- Arquivos-alvo: `services/funil/apps/core/views.py`,
  `services/funil/config/urls.py`, templates, traducoes quando houver texto de
  tela e testes.
- Somente leitura: contrato do catalogo, `infra/traefik/dynamic/plataforma.yml`.
- Dependencias: Frente 1; pode usar mock do contrato enquanto Frente 2 roda.
- Contratos: sem mudanca propria.
- Provas: `/flp-0` 200 com pagina publicada, 404 sem publicacao, 503 com
  catalogo mudo, corpo fora do contrato nao vira 500, UTM preservada nos CTAs,
  telemetria com slug e versao.
- PR proprio: sim.
- Riscos: duplicar renderer de `/oferta`; rota localizada sem classificacao.
- Armadilhas: rota nova no funil passa pela matriz de idioma; classificar como
  pagina ou maquina antes de existir.

### Frente 5 - mapa e publicacao

- Objetivo: tornar a pagina encontravel no mapa humano e conferir URL publica.
- Branch/worktree: `agent/admin/funil/mapa-flp-0`.
- Arquivos-alvo: `painel/mapa-do-site.json`, registros e provas de publicacao.
- Somente leitura: rotas de admin, funil e Traefik.
- Dependencias: Frente 3 ou Frente 4, conforme o que entrar primeiro.
- Contratos: nenhum.
- Provas: `python ci/mapa_do_site.py`, URL `https://meshcraft.top/flp-0` e
  URL privada conferidas depois do deploy.
- PR proprio: sim, quando nao couber nos PRs donos das rotas.
- Riscos: mapa declarar pagina antes da rota existir.
- Armadilhas: registro verde exige evidencia e `verificado_em`.

## 9. Nao fazer

- Nao mover o clone fechado do admin para a internet publica.
- Nao criar Traefik por pagina.
- Nao colocar checkout, cobranca ou captura propria dentro desta fase.
- Nao criar varios caminhos publicos para o mesmo modelo.
- Nao editar o clone original em `C:\Users\davia\paginas\fl-gpt`.
- Nao trocar `/oferta` ou a home por `/flp-0`.

## 10. Estado

Decisao executavel registrada em 24/09/2026.

Esta fase nao implementa codigo de celula. O proximo gesto seguro e a Frente 1,
porque ela fixa a fronteira sem fazer `admin`, `catalogo` e `funil` adivinharem
formas diferentes para o mesmo JSON.
