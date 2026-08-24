# PROJETO I18N — a plataforma em vários idiomas

**Data:** 23/08/2026 (plano original) · **atualizado 23/08/2026 à noite** com o
veredito da consulta (§6) e o **"segue" do mantenedor** — as decisões abaixo são
**FINAIS** para as fases 1–3; nenhum marcador `[CONSULTA]` resta.

**Mandato:** preparar o meshcraft.top para vários idiomas — padrão **inglês**,
`pt-br` e `es` desde já (outros `pt-*` depois), começando pela página de
cadastro. Critérios: escalável, sustentável, operável por agentes de IA.

**Como este documento chegou aqui:** o plano original foi submetido a 4 IAs
(pareceres em `docs/i18n/recomendação-*.txt`), as respostas foram analisadas por
um comitê de 4 revisores especializados com verificação empírica contra o
repositório e a máquina, e a consolidação passou por uma revisão final do
mantenedor que corrigiu 3 pontos, fechou 1 lacuna grave e acrescentou 4
omissões. O registro completo — incluindo os ERROS dos pareceres, para nenhum
agente futuro copiá-los — está no §6.

---

## §1 — O que existe hoje (diagnóstico medido, 23/08/2026)

- **Quem serve as páginas do meshcraft.top é a célula `funil`** — router
  catch-all do Traefik (`PathPrefix('/')`, priority 1). `/en/cadastro`,
  `/pt-br/cadastro` e `/es/cadastro` chegam ao funil **sem tocar o Traefik**.
- **meshcraft.top está no ar** (Modo B, Let's Encrypt direto, sem CDN de HTML
  na frente) como "site de testes" — **nada indexado a proteger**: é o momento
  mais barato da história da plataforma para acertar URLs.
- **Não existe NENHUMA infraestrutura de idioma.** Textos fixos em PT-BR nos
  templates; `base_mobile.html` crava `<html lang="pt-br">`.
- **Site é dado, não código** ([INV-P11]/CONV-SITE): `infra/sites.json` é o
  registro declarativo; **o Traefik NÃO decapa prefixo nenhum — a request line
  chega inteira à célula** (lição paga, ARMADILHAS §4.10). Idioma segue o mesmo
  padrão: dado do site.
- **Os nomes de produto/oferta JÁ nascem versionados em `infra/sites.json`** e
  convergem ao catálogo por `infra/sincronizar_sites.py` — fato decisivo para o
  D7.
- **A célula `alunos` não tem cadastro público**; identidade do aluno é a
  conversa EVO-01 (Caixa de Sugestões). Este plano não a decide.
- **Restrições:** orçamento de 15 arquivos (com válvula por label em
  `ci/orcamento-de-mudanca.sh`); templates Django + ilhas Alpine sem build
  step (R6); Traefik **v3.4**; máquina de dev Windows; quem escreve e traduz é
  agente de IA em PR pequeno.

---

## §2 — Decisões de desenho (FINAIS)

### D1 — URL: TODOS os idiomas com prefixo, inclusive o inglês

```
meshcraft.top/en/cadastro       → inglês (padrão do site, COM prefixo)
meshcraft.top/pt-br/cadastro    → português do Brasil
meshcraft.top/es/cadastro       → espanhol
```

Decisão unânime das 4 IAs consultadas, contra o plano original — e endossada:
mudar o idioma padrão no futuro vira **uma linha de dado**, não migração de
301 em massa ("identidade persistente de recurso"); "ausência de prefixo
também é um idioma" era uma exceção invisível que reapareceria em dezenas de
lugares onde agentes geram URL; e hoje não há nada indexado — trocar é grátis.

Regras de borda (a "matriz HTTP", toda ela vira teste):

- **Raiz `/` de site multilíngue:** `302` fixo e determinístico para
  `/{default}/` — **nunca 301** (301 fica cacheado no navegador e travaria a
  troca de default) — com **`Cache-Control: max-age=300`** (o redirect é
  determinístico por decisão nossa — não varia por usuário — logo É cacheável;
  `no-store` obrigaria round-trip à origem no caminho de maior volume de um
  funil de tráfego pago; max-age curto propaga uma troca de default em
  minutos). Só GET/HEAD; query preservada.
- **Caminho nu** (`GET /cadastro`): `302` para `/{default}/cadastro`
  (preserva link curto de marketing). **Métodos não-GET: `404`** — 301/302
  fazem o navegador converter POST em GET e descartar o corpo em silêncio; se
  um dia for preciso redirect preservando método, é 307/308.
- **Caixa e forma:** só minúsculo é válido (`/pt-br/`); `/pt-BR/`, `/PT-BR/`,
  `/pt_br/` ⇒ `404` (fail-closed; nada nunca linkou para essas formas).
- **Prefixo não habilitado para o site** (`/fr/cadastro`) e prefixo
  desconhecido ⇒ `404`.
- **Sem negociação de `Accept-Language` em lugar nenhum** (recomendação
  documentada do Google; o Googlebot normalmente nem envia o header; `Vary:
  Accept-Language` estilhaça cache). Melhoria futura: banner client-side
  ("Ver em Português?") via ilha Alpine + cookie — e **cookie nunca muda o
  conteúdo servido numa URL fixa**.
- **Invariante-teste: uma URL = um idioma** — a mesma URL requisitada com
  `Accept-Language` opostos devolve **bytes idênticos**.
- **Modo por site é dado** (`i18n_mode`): site sem declaração = monolíngue sem
  prefixo, comportamento atual **intocado por construção**.
- **Resolver próprio** de prefixo (poucas linhas, testável) — **não**
  `i18n_patterns`: a configuração dele é global por settings (um
  `LANGUAGE_CODE`, uma lista), inaplicável a um serviço que atende N sites com
  conjuntos e defaults diferentes por Host. O resolver chama
  `django.utils.translation.activate(locale)` por requisição (ver D2.4).
- Registrada para o dia em que houver CDN: **identidade de cache = site +
  locale + rota**, nunca só o path (funil multissite ⇒ path sozinho é
  envenenamento cross-site garantido).

### D2 — Catálogo: YAML **key-major** (um arquivo por página, idiomas dentro) + tag `{% t %}`

```
services/funil/traducoes/
  cadastro.yaml     ← todas as línguas desta página, lado a lado
  comum.yaml        ← chrome de UI comprovadamente invariante (pequeno, vigiado)
```

```yaml
titulo:
  _fonte: a3f9c1          # 6 hex do sha256 do valor en no momento da tradução
  en: "Start building games"
  pt-br: "Comece a criar jogos"
  es: "Empieza a crear juegos"
```

Por quê key-major (e não um arquivo por idioma, como no plano original):
página nova = **1 arquivo, tenha o site 3 ou 15 idiomas** (resolve a tensão
com o teto de 15 por construção); conflito de merge entre agentes em páginas
diferentes fica estruturalmente impossível; o tradutor-IA vê a fonte inglesa
no mesmo hunk do diff; o `_fonte` mora ao lado das traduções. Reversível
(locale-major p/ TMS = script de ~50 linhas).

Regras do formato ("MessageSpec", não `dict[str, str]`):

1. Valor é **string**, OU **submapa de plural** com as categorias CLDR
   **daquele idioma** (via `babel`, Python puro — en: `one/other`; pt/es
   modernos incluem `many`; o portão consulta o babel pinado, nunca lista
   hardcoded), OU chave com sufixo **`.html`** — a única que admite markup,
   com whitelist de tags; todo o resto é escapado por padrão.
2. **Placeholders nomeados** `{var}`, restritos a `[a-z_][a-z0-9_]*` — sem
   ponto/índice (bloqueia `{user.senha}` via `str.format`). Conjunto de
   placeholders idêntico entre todos os idiomas de cada chave.
3. **`{% t %}` só aceita literal** (lint) — chave dinâmica cega a análise
   estática.
4. **O runtime i18n do Django fica LIGADO** mesmo sem usarmos `.po` próprios:
   `translation.activate()` por request dá erros de formulário, `humanize` e
   formatos localizados de graça (o pip já embarca os `.mo` do framework —
   zero binário). A primeira página é um formulário; isso apareceria no dia 1.
5. **`t(chave, idioma, **kwargs)` é função Python primeiro**, a template tag é
   casca — e-mails e workers a reutilizam. `t_lazy` (2 linhas com
   `django.utils.functional.lazy`) para labels avaliados em import.
6. **Ilhas Alpine:** subárvore `js.*` por página, emitida com
   `{{ ...|json_script }}`; proibido catálogo de tradução em JS. Formatação
   client-side usa a `Intl` nativa do navegador lendo `<html lang>`.
7. **YAML "chato"**: `safe_load` com loader que **rejeita chave duplicada**
   (o PyYAML aceita em silêncio — verificado), sem anchors/aliases/tags;
   **toda folha é `str`** (mata `no`/`yes`/`on` virando booleano e `12:30`
   virando 750 — verificado no PyYAML 6.0.2); **as chaves de idioma parseadas
   têm de ser exatamente as strings de `IDIOMAS_BASE`/`VARIANTES`** (o
   `idiomas_conhecidos` que o `achatar()` recebe) — no dia em que
   existir norueguês, `no:` viraria `False` como CHAVE antes de qualquer
   validação de folha; com esta regra, cai como tipo inválido de chave.
8. **Chaves semânticas imutáveis**: a chave nomeia o papel
   (`cadastro.cta_primaria`), nunca o texto; mudança de copy não renomeia
   chave. Reuso entre contextos só com identidade semântica real (duplicar é
   melhor que acoplar — "Continuar" espanhol pode precisar ser
   "Seguir"/"Avanzar" por contexto). Comentários YAML carregam contexto para
   o tradutor.

Por que não gettext (justificativa corrigida pela consulta): (a) **msgid é a
chave** — agente ajusta uma vírgula no inglês e invalida N traduções (churn
fuzzy permanente); (b) **os comandos de gerência do Django exigem binários
GNU** (`makemessages` chama `xgettext` — verificado no Django 5.1; extração
pura-Python existe no `pybabel extract`, mas para template Django depende de
plugin de terceiros abandonado); (c) uma frase alterada toca N arquivos `.po`
contra o teto de 15. "Falha aberto" é motivo secundário (corrigível com
`polib`). Rejeitados com motivo: Fluent (ecossistema Python parado/Alpha;
`{% t %}` como costura torna migração futura um script), JSON i18next (perde
comentários = perde contexto), PyICU (binário C — mesmo critério do gettext),
banco para copy de UI (fora do alcance do CI).

### D3 — Idioma é dado do site ✅ (fechado na fase 4, 24/08/2026)

Idioma de site é dado do **catálogo**: declarado em `infra/sites.json`,
convergido para a produção pelo `deploy-infra`, servido pela API do catálogo sob
o contrato `contracts/catalogo.openapi.yaml` (schema `Site`). Dois campos, e só
dois:

```yaml
default_language: "en"                            # ausente ⇒ monolíngue
languages: [{code: "pt-br", indexable: true}]     # ausente/vazio ⇒ monolíngue
```

Site sem os dois = monolíngue como hoje: nenhuma URL ganha prefixo. A célula lê
os idiomas do `Site` que o `SiteResolutionMiddleware` já resolve por Host
([INV-P11]), uma vez por janela de cache — zero trabalho por requisição.

**O interim `services/funil/sites_i18n.yaml` morreu aqui** (PRs #104/#106/#107):
o arquivo foi apagado, e com ele o teste de coerência que o vigiava — não há
mais dois lugares declarando, então não há mais o que cruzar. A aposentadoria
tem guarda mecânica: `services/funil/tests/test_i18n_catalogo.py` reprova se o
arquivo voltar a existir.

O interim declarava CINCO coisas; o contrato recebeu **duas**. As outras três
não podiam virar campo de site, porque não variam por site:

- **tag BCP 47** (`pt-br` → `pt-BR`) e **`dir`** (`ltr`/`rtl`) **derivam do
  código do idioma** (`apps/i18n/idiomas.py`: `tag_bcp47()`, `direcao()` sobre a
  tabela `IDIOMAS_RTL`). Como dado por site seriam N lugares para escrever a
  mesma verdade — e N para escrevê-la errado: `dir: rtl` num site em inglês
  passaria pelo contrato e quebraria a página.
- **base da variante** (D4) vive em `apps/i18n/catalogo.py` → `VARIANTES`, e o
  **glossário** (D8.1) ao lado, em `GLOSSARIO`: são política de TRADUÇÃO da
  célula. Dois sites que sirvam `pt-pt` caem no mesmo `pt-br` porque o texto é o
  mesmo, não porque cada um configurou isso.

Regra de bolso que sobrou: **o contrato carrega o que varia por site; a célula
carrega o que varia por idioma ou por catálogo de tradução.** Antes de propor
campo novo no contrato do catálogo, pergunte se dois sites poderiam querer
valores diferentes — se não poderiam, o campo é da célula.

### D4 — Paridade em dois níveis + `_fonte` anti-obsolescência

- **Idiomas-base** (`en`, `pt-br`, `es`): paridade **exata** — falta E sobra
  reprovam, nas duas direções (template↔catálogo: o conjunto de chaves usadas
  em `{% t %}` + `js.*` é **exatamente igual** ao definido — pega o typo que a
  paridade entre idiomas não vê).
- **Variantes regionais** (`pt-pt`…): overlay esparso com **base declarada
  como dado** (`pt-pt: {base: pt-br}`) — **sem `pt` neutro** (não existe nem
  existirá conteúdo pt genérico; criá-lo só para ser ancestral produziria
  pseudo-português artificial), **nunca derivada da tag BCP-47**, **máximo 1
  nível** (variante → base → en; fallback de fallback = ERROR). CI do overlay:
  toda chave existe na base; valor obrigatoriamente **difere** da base;
  placeholders batem. Ausência em overlay = herda (válido); ausência em base =
  vermelho. Grafo declarado, acíclico, terminando em base com paridade plena.
- **`_fonte`** (hash da fonte): CI reprova quando `_fonte != hash(en)` —
  inglês mudou ⇒ traduções daquela chave estão obsoletas até reconciliar.
  Estado **`pendente`** explícito: cai no fallback e conta — degradação
  **declarável, nunca inferível**.
- **Regra anti-burla (obrigatória — sem ela o `_fonte` é lembrete, não
  portão):** se `_fonte` de uma chave **mudou no diff**, todos os valores
  não-base daquela chave têm de ter mudado também, OU estar `pendente`, OU a
  linha carregar o marcador explícito `# revisado-sem-alteracao` (o caso
  legítimo: typo no inglês que não altera as traduções — auditável, greppável,
  contável). Recalcular o hash sem traduzir deixa de ser o silenciador barato
  que um agente instruído a "deixar o CI verde" acharia primeiro.
- **Boot fail-closed:** o validador inteiro (formato + integridade + `_fonte`
  + fallback) roda também na inicialização da célula e **recusa subir** com
  catálogo inválido — CI protege o merge; o boot protege a produção (merge
  sujo, drift). De brinde: catálogo achatado imutável em memória, zero parse
  por request. **Nota de rollback:** o deploy por compose recria o container —
  se um catálogo inválido escapasse do CI, a célula ficaria fora do ar até o
  revert (revert do merge ⇒ deploy). Aceitável porque CI + portão de deploy
  tornam o caso quase impossível — mas está escrito, para ninguém descobrir
  na hora.
- **Produção:** chave ausente cai pela cadeia com **ERROR + contador**
  (log estruturado com site/locale/chave; métrica quando houver stack de
  métrica), nunca warning perdido.

### D5 — SEO desde a primeira página

O `base_mobile.html` do funil emite, por página, tudo gerado dos idiomas do
site (D3) — hoje por `idiomas.dados_seo()`, nunca à mão:

- `<html lang="pt-BR" dir="ltr">` (tag BCP 47; URL continua minúscula — cada
  convenção no seu lugar, com canonicalização interna única: nosso teste de
  reciprocidade compara strings e o lookup no registro erra se as formas
  divergirem — a exigência é interna, não do buscador).
- **Canonical auto-referente**, absoluto, `https`, com o **host canônico do
  Site resolvido — nunca `request.get_host()`** (senão domínio de preview
  vaza para o hreflang de produção). Teste explícito do anti-padrão:
  canonical de `/pt-br/*` apontando para a versão inglesa = reprovado.
- **hreflang recíproco, auto-incluído, absoluto**, um por idioma habilitado
  **e indexável** do site + **exatamente um `x-default`** por página →
  a URL `/en/` da MESMA página (x-default é por cluster de página, não do
  site). **Canal único: as tags `<link>` no HTML** — dois canais (HTML +
  sitemap) divergem em silêncio e sinal conflitante é descartado.
- **`<title>`, meta description e og:title/description por idioma** — chaves
  normais do catálogo, cobertas pela paridade. `og:locale` em formato
  underscore (`pt_BR`) + `og:locale:alternate`.
- **Seletor de idioma é `<a href>` real** — JS por cima, nunca no lugar: com
  hreflang só no HTML, versão sem link rastreável pode nunca ser descoberta.
  Teste: **toda URL alternativa do hreflang aparece como `href` de âncora na
  página renderizada.**
- **`indexable` por idioma é DADO** (D3 — campo do contrato, default `true`) e
  controla `noindex` + exclusão do hreflang/sitemap. **Aplicando a própria
  regra "3 idiomas bons antes do 4º": o `es` NASCE `noindex`** — o público
  inicial é brasileiro; espanhol no
  dia 1 em domínio novo com tradução de agente é exatamente o padrão que
  classificador de spam procura. Constrói-se já; indexa-se quando houver
  razão de demanda (custa flipar um dado).
- **Slug: `cadastro` fica** — o valor SEO da palavra no slug é marginal
  (posição pública do Google), e a URL é a do mandato. Regra: **slug único
  entre idiomas** (não traduzido), **rota resolvida por ID de página** com o
  slug como apresentação — deixa slug traduzido como opção barata futura em
  vez de migração de 301.
- Fase 2: `sitemap.xml` simples (todas as URLs indexáveis de todos os
  idiomas, sem `xhtml:link`) + envio ao Search Console.
- Ignorar com consciência: `Content-Language` (o Google determina idioma pelo
  conteúdo visível — não gastar uma linha), redirect por geo-IP (nunca),
  sitemap particionado por idioma (dezenas de URLs primeiro).

### D6 — Roteamento além do funil: DECIDIDO agora, implementado quando precisar

- **Congelado: locale-first** — `/{locale}/{célula}/...`. Rejeitado
  `/checkout/pt-br/` por unanimidade (duas gramáticas de URL no mesmo site;
  topologia interna não dita URL pública).
- **Mecânica registrada** (Traefik v3.4, quando a primeira página fora do
  funil precisar): a regra da célula vira
  `` PathRegexp(`^/[a-z]{2}(-[a-z]{2})?/checkout(/|$)`) || PathPrefix(`/checkout`) ``
  — regex de **formato com fronteira** (sem a fronteira, `/pt/checkout-tips`
  cairia na célula errada), mesma priority. O gateway casa a forma; **a
  aplicação valida** contra os idiomas do site (rotas são host-agnósticas —
  precisão por site é impossível no gateway e já é o padrão CONV-SITE).
- **SEM decapar o prefixo no gateway** — path completo até a célula (regime
  real e já pago do repo, ARMADILHAS §4.10); a célula copia o resolver do
  funil (Lei 7). Rejeitado o contrato `X-Locale`/`X-Language` por strip:
  Traefik stock não injeta header com valor dinâmico do path, e o strip
  criaria dois regimes de path convivendo.
- **Rotas de máquina nunca se localizam:** `/api/**`, `/webhooks/**`,
  `/static/**`, `/healthz` não ganham prefixo de idioma — o desenho atual já
  obedece por construção (`/pt-br/api/...` não casa a priority 20 e morre
  404 no funil); a regra escrita impede alguém de "consertar" isso. Teste.
- **Nenhum prefixo de célula novo pode ter formato de locale** (2–3 letras ±
  região) — teste; vale dobrado porque `PathPrefix` casa prefixo de string
  cru.
- **Pendência registrada:** helper de link cross-célula (host canônico +
  idioma ativo + prefixo da célula) — `{% url %}` não atravessa serviços;
  decidir junto com a primeira página multilíngue que linkar para fora do
  funil.
- **Área autenticada** (`alunos`, pós-EVO-01): idioma por URL ou por perfil
  do usuário é decisão **explícita** na hora, por classe de rota — não
  herança automática deste esquema.

✅ **Os três guardas acima viraram teste em 24/08/2026** (despacho
`funil/guardas-d6`), e valem **independentemente** de a fase 5 ser ativada — é
justamente por isso que foram escritos com o resto da fase 5 congelado:

| guarda | onde vive | por que ali |
|---|---|---|
| prefixo de rota com forma de locale | `ci/tests/test_rotas_sem_forma_de_locale.py` | a mudança que ele pega toca `infra/`, e o `ci-celula` só roda o `make ci` de uma célula quando o diff tem `services/<celula>/…` — na célula o guarda seria decoração no único PR para o qual existe. Em `ci/tests` roda em TODO PR (workflow `muralhas`), e é o único lugar de onde se enxergam as duas pontas da colisão: a tabela de rotas **e** `infra/sites.json` |
| rota de máquina nunca se localiza | `services/funil/tests/test_d6_roteamento.py` | comportamento da célula, medido contra o middleware e o urlconf reais |
| link cross-célula sem prefixo | `services/funil/tests/test_d6_roteamento.py` | idem — varre a página renderizada nos 3 idiomas |

Dois achados da implementação, onde o D6 supunha outra coisa:

- **O guarda de rota precisou de uma segunda regra, com dado.** Só a FORMA
  errava nas duas direções: reprovava `/api/checkout` (o `api` tem 3 letras e
  casa `[a-z]{2,3}`) e deixaria passar um idioma longo (`zh-hant-tw`). O teste
  cruza os prefixos com os idiomas realmente declarados em `infra/sites.json`
  — a colisão de verdade, que cresce sozinha a cada idioma novo — e mantém a
  forma como rede para o futuro, com os namespaces de máquina do próprio D6
  (`api`, `webhooks`, `static`, `healthz`) isentos **da forma, nunca da
  colisão**.
- **"O desenho atual já obedece por construção" vale para `/api/**`,
  `/webhooks/**` e `/sitemap.xml` — e NÃO vale para `/healthz`.** A isenção do
  middleware casa o `path_info` cru, então `/pt-br/healthz` não é isenta: o
  resolver decapa o prefixo e o urlconf serve a view. Medido: **200**, hoje.
  Vale para qualquer rota de máquina que o próprio funil sirva sem estar em
  `CAMINHOS_DE_MAQUINA`. Está fixado como `xfail(strict=True)` no teste da
  célula — no dia em que consertarem, ele fica vermelho por XPASS e obriga a
  apagar o marcador; o desvio não some em silêncio. O conserto é uma linha em
  `apps/core/middleware.py` e **precisa de mandato próprio**: `apps/**` estava
  somente-leitura no despacho dos guardas.

### D7 — Conteúdo que é dado: tradução DENTRO do `sites.json`

Os nomes de produto/oferta já nascem em `infra/sites.json` e convergem por
`sincronizar_sites.py`. A tradução entra **na própria declaração**
(`"name": {"en": …, "pt-br": …}` + hash de fonte) e flui até **JSONB** no
catálogo — o dado traduzível continua passando por PR, diff e portão de
paridade, e o buraco "CI de git não alcança banco" **não chega a nascer**.

- **Política de ausência por campo**, declarada e validada no
  `sincronizar_sites.py` (fail-closed no deploy): fallback pela cadeia,
  esconder o item, ou bloquear publicação.
- **Um único helper** de leitura com a MESMA cadeia de fallback das strings
  de UI (duas implementações divergindo em silêncio = bug garantido).
- **Identificador nunca se traduz** (slug de produto, SKU) — separar
  identidade de conteúdo. "O que falta traduzir" é query de uma linha
  (`WHERE NOT (name ? 'es')`).
- **Gatilhos de migração para tabela relacional** (deixa de ser JSONB quando
  aparecer QUALQUER um): slug público por idioma, publicação/aprovação por
  locale, workflow de tradutor humano, busca indexada por locale, auditoria
  por tradução. Microsserviço de tradução: não (unânime).

### D8 — Qualidade e segurança de conteúdo (novo, da revisão final)

Os portões estruturais (paridade, `_fonte`, placeholders, boot,
pseudo-locale, matriz HTTP) verificam **integridade** — nenhum verifica se a
tradução **está boa**. Para página de cadastro de curso pago, copy é o
produto; o risco residual concentra-se no único lugar sem portão. Defesas:

1. **Glossário de não-traduzir**: lista de termos protegidos (Meshcraft,
   Roblox, Roblox Studio, nomes de produto) + check mecânico de presença
   literal em toda tradução. Agente traduz nome de marca com entusiasmo e a
   paridade fica verde — este é o validador de maior taxa de acerto por linha
   de código.
2. **Namespace jurídico**: termos de uso, privacidade, consentimento —
   marcador `_juridico: true`; o CI **reprova** publicação sem marcador de
   revisão humana. Texto com efeito legal traduzido por agente em N
   jurisdições é risco de responsabilidade, não de conversão.
   ✅ **IMPLEMENTADO 23/08/2026** (despacho funil/i18n-juridico): no catálogo
   escreve-se `_juridico: "true"` (com aspas — toda folha é `str` por D2.7), e
   a chave **só passa** com `_revisado_humano`, um mapa **idioma → "Quem
   revisou AAAA-MM-DD"** com uma entrada por idioma da chave, e com `_fonte`
   fora de `pendente`. A granularidade é **por idioma** porque revisar o inglês
   não valida o espanhol; e a declaração **expira no diff** — texto jurídico
   que muda num idioma exige declaração nova daquele idioma (mesma mecânica da
   regra anti-burla do `_fonte`, e pelo mesmo motivo). Reprova no CI **e o boot
   recusa subir** (D4). Detalhes em `services/funil/LICOES.md`.
3. **Guardas semânticas como RELATÓRIO no PR** (não gate): razão de
   comprimento (3× ou 0,3× do `en` sinaliza — pega truncamento e alucinação);
   retrotradução com modelo diferente (sinaliza divergência — pega negação
   invertida e cláusula perdida).
   ✅ **Razão de comprimento IMPLEMENTADA 23/08/2026** como relatório puro
   (`Resultado.avisos`: WARNING no boot e sumário de warnings do pytest no
   `make ci`; nunca muda PASS/FAIL), com piso de 12 caracteres no `en` para não
   sinalizar rótulo curto legítimo (`E-mail` → `Correo electrónico` já é 3×).
   ⛔ **Retrotradução: NÃO implementada, e não deve ser simulada.** Ela exige
   chamar um modelo externo — chave de API, custo por PR, escolha de provedor —
   e isso é **decisão do mantenedor**, não de agente. Enquanto não houver
   decisão, a defesa contra negação invertida e cláusula perdida é a revisão
   humana do item 2; nenhum stub deve fingir que a checagem existe.
4. **Pseudo-locale nos testes**: renderizar em idioma sintético (`en` inflado
   40% com acentos) e reprovar texto visível sem a marca — detector mecânico
   de string hardcoded + layout estourado.
5. **Limite honesto, registrado como risco estrutural ABERTO (não como
   mitigado):** o mantenedor não lê inglês — o idioma-fonte da página de
   maior valor **não é auditável internamente**. O `pt-br` fiel (tradução
   sempre literal ao sentido, nunca "adaptação criativa") é a janela de
   auditoria dele, e a revisão adversarial de copy por segundo agente ajuda —
   mas IA revisando copy de IA para conversão não tem verdade de referência.
   O que resolve é **humano nativo ou dado de mercado (conversão medida)**.
   Nenhuma arquitetura conserta isso.

### D9 — Processo e portões (novo)

- **Lane `traducoes` no orçamento de 15 arquivos**: extensão de ~10 linhas em
  `ci/orcamento-de-mudanca.sh` (que já tem a válvula `arquitetural`) — PR
  pode exceder 15 arquivos **somente se** todo o diff casar
  `services/*/traducoes/**` (zero arquivo executável) E os validadores i18n
  estiverem verdes. Mede superfície de risco, não contagem bruta.
- **Dois fluxos de PR nomeados** (entram na R12): página nova nasce com
  **todos** os idiomas do site no mesmo PR (a paridade já força; key-major
  faz custar 1 arquivo); idioma-base novo em site grande = lote
  translation-only pela lane, ou sequência com `indexable: false` até
  completar.
- **CSS com propriedades lógicas** (`margin-inline-start`, `text-align:
  start`) + o `dir` **derivado do código do idioma** (`idiomas.direcao()`) em
  todo CSS novo — regra da R12; RTL futuro não precisa de dado novo nenhum: a
  tabela `IDIOMAS_RTL` já responde `rtl` para `ar`/`he`/`fa`/… pelo código.
- **Idioma ≠ mercado ≠ moeda ≠ timezone**: campos separados no contrato do
  site desde já, mesmo com defaults triviais (es não implica EUR; dinheiro
  segue `(centavos, moeda ISO)`).
- **Idioma do lead é dado de negócio**: o cadastro captura o idioma da
  requisição — interim sem tocar contrato:
  `source="cadastro-meshcraft-<locale>"`; campo próprio quando houver Rito.
  Lead sem idioma não tem retrofit.
- **Mensageria/eventos**: e-mails transacionais têm copy PT-BR fixa em dict
  Python e nenhum evento de `contracts/eventos/` carrega locale (medido —
  continua verdade em 24/08/2026). Estava registrado para a fase 4; **ficou de
  fora dela por decisão** (§4, a nota abaixo da tabela de fases): os 5 esquemas
  são `additionalProperties: false` ⇒ campo novo é breaking, e 4 dos 5 são do
  fluxo de pagamento, hoje fechado por diretiva do mantenedor. Fase própria,
  quando houver motivo de negócio.
- **Texto dentro de imagem é dívida**: hero com frase em inglês = um asset
  novo por idioma; texto fica em HTML. Fonte: stack de fallback +
  `unicode-range` quando houver primeiro idioma não-latino declarado.
- **Experimento de copy não se traduz** (princípio guardado — ver §6 sobre
  "Copy Lab"): variante existe só no idioma-base, vencedor promovido e só
  então traduzido; namespace de experimento isento de paridade e `noindex`.

---

## §3 — A página de cadastro: o que entra já, o que espera o EVO-01

**Fase já:** `/en/cadastro`, `/pt-br/cadastro`, `/es/cadastro` no funil
(es `noindex` — D5) — formulário nome + e-mail (+ WhatsApp opcional),
postando server-side para `leads` com
`source="cadastro-meshcraft-<locale>"` (D9). Erros de validação saem no
idioma da página via `translation.activate()` (D2.4).

**Fase que espera:** identidade do aluno = EVO-01 (link mágico por e-mail).
Nada da fase 1–2 é jogado fora.

## §4 — Fases (cada uma = 1 PR dentro do orçamento; lane `traducoes` para lotes)

| Fase | Entrega | Depende de |
|---|---|---|
| **1** ✅ | **ENTREGUE** — Fundação no funil: resolver de prefixo + matriz HTTP + `activate()`; registro **interim** `sites_i18n.yaml` (com `dir`, `base`, `indexavel`, tag BCP 47) + teste de coerência com `sites.json` — **os dois aposentados na fase 4**, o idioma passou a vir do catálogo (D3); `t()`/`{% t %}`/`t_lazy`; o portão no molde do `contract_freeze.py` (PASS/FAIL/ERROR — formato, paridade exata, template↔catálogo, placeholders, plural CLDR, `_fonte` + regra anti-burla, overlay, glossário, pseudo-locale) rodando no CI **e no boot** — nasceu como `apps/i18n/validador.py` dentro do `make ci` da célula, **não** como `ci/i18n_check.py` na raiz; `base_mobile` com lang/dir/canonical/hreflang/seletor-`<a href>` | **nada — o "segue" foi dado em 23/08** |
| **2** ✅ | **ENTREGUE** (no ar desde 23/08, matriz medida de fora) — Página `/[en\|pt-br\|es]/cadastro` (template + `traducoes/cadastro.yaml` + view + testes), POST a leads com locale, `sitemap.xml` (rota de máquina, `apps/core/views.py`). O **envio ao Search Console** é passo do mantenedor e não consta como feito | fase 1 |
| **3** ✅ | **ENTREGUE** — **Receita R12** no `CAMINHO-DOURADO.md`: os dois fluxos de PR (página nova / idioma novo), passo a passo verificado contra o código da fase 1–2, contrato do `_fonte` + regra anti-burla, checklist das 10 regras do validador, o que a máquina NÃO protege (D8), CSS com propriedades lógicas, armadilhas por número. Registrado ali o que a implementação real ainda NÃO tinha: o marcador `_juridico` do D8.2 e a lane `traducoes` na catraca `mergear.py` — **os dois fechados em 23/08/2026** (PRs #95 e #94; ver D8.2, `docs/historico/RESOLVIDAS.md` §5.11 e a §5.15 em `armadilhas/`) | fases 1–2 no ar |
| **4** ✅ | **ENTREGUE 24/08/2026, provada em produção** — idioma no `sites.json`/catálogo/**contrato** e **aposentadoria do interim**: `contracts/catalogo.openapi.yaml` ganhou `default_language` + `languages[{code,indexable}]` pelo Rito de Contrato (**#104**), o catálogo passou a servir os campos (**#106**), o funil passou a lê-los e o `services/funil/sites_i18n.yaml` foi **apagado** (**#107**). Ver D3. ⚠️ **A metade "locale nos eventos/mensageria" ficou de fora DE PROPÓSITO** — não é esquecimento: ver a linha abaixo da tabela | mandato próprio (dado em 24/08) |
| **5** ❄️ | **CONGELADA por decisão do mantenedor (24/08/2026)** — D6 (internacionalizar célula além do funil) e D7-tabela se gatilho disparar. **Motivo:** não há alvo legítimo hoje — `checkout` é pagamento (diretiva do mantenedor: não tocar até o site vender), `quiz` não é declarado por site nenhum em `infra/sites.json`, `alunos` não tem página. **O que destrava:** a primeira página real fora do funil que precisar de idioma. Os **guardas do D6 já estão no ar** e independem da ativação (ver D6) | necessidade real |

A fase 1 não muda a landing atual em nada (site sem `languages` no catálogo =
monolíngue por construção; teste de regressão prova). Continua valendo depois
da fase 4: o que era "fora do registro" hoje é "sem os dois campos no `Site`".

**Por que a fase 4 fechou pela metade, e por que a metade certa.** O `locale`
nos eventos/mensageria **não** entrou, por decisão, não por falta de tempo:
os 5 esquemas de `contracts/eventos/` são `additionalProperties: false`, então
acrescentar um campo é **breaking** — exigiria `.v2.json`, emissão dupla e a
migração das 4 células consumidoras (`alunos`, `checkout`, `leads`,
`mensageria`). Além disso, 4 dos 5 esquemas são do fluxo de pagamento/pedido,
área que o mantenedor mandou **não tocar até o site vender**. Fica como fase
própria, com mandato próprio, quando houver motivo de negócio — e o interim do
D9 (`source="cadastro-meshcraft-<locale>"`) segue carregando o idioma do lead
sem tocar contrato nenhum.

**Este projeto está ENCERRADO em 24/08/2026.** Fases 1–4 entregues e no ar; a
fase 5 congelada acima. Congelar não é abandonar: os três guardas do D6 foram
escritos e estão vermelhos-quando-devem (a prova está no PR do despacho
`funil/guardas-d6`), então o roteamento de hoje não quebra em silêncio enquanto
ninguém olha. O dia em que a fase 5 destravar, quem a ativar vai **descobrir
pelos próprios testes**: o guarda de link cross-célula e o de matcher
desconhecido no gateway ficam vermelhos de propósito e mandam descongelar isto
aqui antes de mergear.

## §5 — O que precisa do mantenedor · o que NÃO precisa

**Nada para as fases 1–4** — o "segue" foi dado em 23/08/2026 (com as
correções da revisão final incorporadas aqui) e o mandato do Rito de Contrato
da fase 4 foi dado em 24/08/2026 e já foi exercido (#104). Continuam dele: a
conversa EVO-01 (identidade); a decisão de negócio que reabriria o `locale` nos
eventos (fluxo de pagamento — hoje fechado por diretiva); e — quando possível,
sem bloquear nada — **um falante nativo de inglês (ou dado de conversão) para o
risco estrutural do D8.5**, que nenhum portão cobre.

---

## §6 — Registro da consulta (23/08/2026) — leitura obrigatória antes de citar os pareceres

**O rito:** 4 pareceres (`recomendação-{sonnet,opus,gemini,gpt-5-6-sol}.txt`)
→ comitê de 4 revisores especializados (URL/roteamento, formato, SEO,
dados/escala) com **verificação empírica** contra o repo e a máquina →
consolidação → revisão final do mantenedor (3 correções, 1 lacuna fechada
[a regra anti-burla do `_fonte`], 4 omissões [jurídico, glossário, chave
`no:`, rollback]) → este documento.

**O que a consulta mudou:** D1 (tudo-prefixado — unânime), D2 (key-major +
MessageSpec + `_fonte`), D4 (dois níveis + anti-burla + boot), D5
(completada; slug `cadastro` mantido contra recomendação da consolidação
intermediária), D6 (congelada), D7 (tradução no `sites.json` — achado do
comitê, invisível aos pareceres), D8/D9 (novos).

**ERROS dos pareceres — não copiar (cada um verificado):**

- `recomendação-sonnet.txt` §6: sintaxe de rota do **Traefik v2**
  (`/{lang:...}/checkout`) — removida no v3; o repo roda v3.4. Copiada,
  derruba o deploy. Forma v3 no D6. Também: `não` **não** vira booleano no
  PyYAML (só literais ingleses); o `compilemessages` do Django passa
  `--check-format` (não descarta o caso citado em silêncio); `i18n_patterns`
  global é inaplicável ao multissite por-host.
- `recomendação-gemini.txt`: middleware de header dinâmico
  (`X-Language` do path) **não existe em Traefik stock**; regex sem
  fronteira final casa `/pt/checkout-tips`; JSON no lugar de YAML (argumentos
  de performance irrelevantes; JSON mata comentários=contexto); 302 por
  Accept-Language na raiz (contra recomendação documentada do Google);
  convenção de plural `_plural` (formato legado i18next v1–v3); "hreflang no
  sitemap acelera incrivelmente a indexação" (sem base; e dois canais =
  risco de sinal conflitante).
- `recomendação-opus.txt`: "pybabel elimina os binários GNU" — a afirmação
  exata é: **os binários são exigidos pelos comandos de gerência do Django,
  não pelo formato gettext em Python** (`makemessages` chama `xgettext` —
  verificado; extração pura-Python para template Django só via plugin de
  terceiros abandonado); `y`/`n` isolados **não** viram booleano no PyYAML;
  o contrato `X-Locale` por strip no gateway é inviável em Traefik stock e
  mudaria células existentes; três generalizações de SEO acima do
  documentado (caixa em hreflang não causa descarte — a canonicalização é
  exigência INTERNA nossa, ver D5; par não confirmado cai, não o cluster
  inteiro; x-default para seletor é permitido, apontar direto é apenas
  melhor prática).
- `recomendação-gpt-5-6-sol.txt`: `pt` neutro como ancestral (1ª passada —
  o próprio parecer retratou na 2ª); tabela relacional como PADRÃO para o
  catálogo atual (superdimensionada — a lista de gatilhos dele está correta
  e virou o critério de migração do D7). No SEO foi o parecer mais preciso
  (zero erro factual).
- **"Copy Lab"** (no parecer do Opus): célula **desenhada pelo mantenedor em
  outra conversa, NÃO implementada no repositório** — não foi alucinação do
  parecer; a premissa de agir sobre ela NO REPO é que era falsa. O princípio
  foi guardado no D9 (experimento não se traduz). Calibração para agentes:
  contexto que não está no repo não é necessariamente inventado — mas só o
  repo é acionável.

**Nota de método (da revisão final, registrada para a próxima consulta):**
convergência entre LLMs é evidência mais fraca que convergência entre
humanos — modelos compartilham corpus e casam padrão com a literatura
majoritária; convergência mede **convencionalidade, não correção** para o
caso específico. Aqui a unanimidade calhou de estar certa por razões locais
(nada indexado, default pode mudar, agentes geram URL). O que produziu valor
real foi a **verificação**: rodar o PyYAML, checar a versão do Traefik,
confirmar o `xgettext`, descobrir a válvula do portão já existente e os
nomes de produto já no `sites.json` — cada verificação matou ou corrigiu
conselho que os 4 modelos manteriam por unanimidade. **Se repetir o rito:
menos pareceres, dobro de verificação contra o repositório.**
