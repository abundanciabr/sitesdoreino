# PROJETO I18N — a plataforma em vários idiomas

**Data:** 23/08/2026 · **Mandato:** pedido direto do mantenedor, em sessão:
preparar o site do Meshcraft (meshcraft.top) para vários idiomas — padrão em
**inglês**, e desde já **pt-br** (português do Brasil; outros `pt-*` virão
depois) e **es** (espanhol) — começando pela página
**`meshcraft.top/pt-br/cadastro`**, onde alunos que ele já tem em outros sites
vão se cadastrar. Critérios dele: **escalável, sustentável, e operável por
agentes de IA com o máximo de agilidade** — página nova tem de nascer rápida e
ser fácil de traduzir.

Este documento é o plano. O documento irmão,
`PROMPT-CONSULTA-OUTRAS-IAS.md`, é o prompt que o mantenedor vai colar em
outras IAs para colher segundas opiniões **antes** de implementarmos — as
respostas voltam para cá e podem mudar as decisões marcadas como `[CONSULTA]`.

---

## §1 — O que existe hoje (diagnóstico medido, 23/08/2026)

- **Quem serve as páginas do meshcraft.top é a célula `funil`** — router
  catch-all do Traefik (`PathPrefix('/')`, priority 1, em
  `infra/traefik/dynamic/plataforma.yml`). Qualquer caminho que nenhum prefixo
  de célula (`/quiz`, `/checkout`, `/alunos`, `/api/...`) capturar cai no
  funil. Logo, `/cadastro`, `/pt-br/cadastro` e `/es/cadastro` chegam ao funil
  **sem tocar o Traefik** — bom para começar.
- **Não existe NENHUMA infraestrutura de idioma.** Os textos são fixos em
  PT-BR dentro dos templates (`services/funil/templates/funil/landing.html`:
  "Quero comprar", "Receba novidades"…), e o
  `services/funil/templates/base_mobile.html` crava `<html lang="pt-br">`.
  Nada de `LocaleMiddleware`, nada de arquivos de tradução, nada de idioma na
  URL.
- **Site é dado, não código** ([INV-P11]/CONV-SITE): o middleware resolve
  `Host → Site` no catálogo a cada requisição, e `infra/sites.json` (R11
  mecanizada, DESPACHO-05) é o registro declarativo — o meshcraft.top já está
  lá. **Idioma deveria seguir o mesmo padrão: dado do site, não if no
  código.**
- **A célula `alunos` não tem cadastro público.** O contrato dela
  (`contracts/alunos.openapi.yaml`) só tem `POST /matriculas` (idempotente por
  `order_id`) e `GET /matriculas` — matrícula nasce de pagamento aprovado, não
  de formulário. **Não existe identidade de aluno** (login/senha/sessão), e
  essa decisão já tem dono: é a conversa **EVO-01** da Caixa de Sugestões
  (`docs/caixa-de-sugestoes/ANDAMENTO.md` — proposta: link mágico pelo e-mail,
  sem senha). O cadastro do Meshcraft esbarra na MESMA pergunta — este plano
  não a decide, se encaixa nela (§3).
- **Restrições que moldam tudo:** orçamento mecânico de 15 arquivos por PR
  (ARMADILHAS §5.1); páginas são template Django + ilha Alpine sem build step
  (Receita R6); cada célula tem seu próprio `base_mobile.html` (Lei 7 — copia
  o padrão, não o arquivo); quem escreve e traduz é agente de IA em PR pequeno.

---

## §2 — Decisões de desenho

Cada decisão traz a recomendação e o porquê. As marcadas `[CONSULTA]` são as
que o prompt para outras IAs questiona — implementação só depois de o
mantenedor ler as respostas (ou mandar seguir).

### D1 — Esquema de URL: prefixo de idioma, inglês sem prefixo

```
meshcraft.top/cadastro          → inglês (padrão do site, SEM prefixo)
meshcraft.top/pt-br/cadastro    → português do Brasil
meshcraft.top/es/cadastro       → espanhol
```

- Códigos **BCP 47 minúsculos com região quando importa**: `pt-br` desde o
  primeiro dia (nunca `pt` sozinho), porque o mantenedor já anunciou outros
  `pt-*`. `es` sem região até existir necessidade (`es-mx`…).
- Idioma padrão sem prefixo é o comportamento do
  `i18n_patterns(prefix_default_language=False)` do Django — mas ver D2: a
  recomendação NÃO usa o stack gettext do Django, então o resolver de prefixo
  é nosso (poucas linhas, testável).
- Prefixo desconhecido ou não habilitado para o site (`/fr/cadastro` no
  meshcraft) ⇒ **404**, coerente com o fail-closed do CONV-SITE (host não
  cadastrado = 404, nunca um padrão silencioso).
- `[CONSULTA]` — redirecionar a raiz por `Accept-Language`? Recomendação
  inicial: **não** (conteúdo do padrão em inglês + links visíveis de troca de
  idioma; redirect automático complica SEO e cache).

### D2 — Onde mora a tradução: dicionários YAML por idioma, não gettext `[CONSULTA]`

Duas rotas possíveis:

| | **A: gettext do Django** (`.po`/`.mo`, `{% trans %}`) | **B: dicionários YAML + tag `{% t %}`** (recomendada) |
|---|---|---|
| Padrão da indústria | sim — plurais, ferramentas prontas | não — plural vira convenção nossa |
| Operável por agente | regular — exige `makemessages`/`compilemessages` (binários GNU gettext; risco de virar linha nova no §1 do ARMADILHAS nesta máquina Windows) | **total** — arquivo de texto puro, agente edita e o diff do PR mostra exatamente o que mudou |
| Fail-closed | fraco — chave sem tradução cai para o msgid em silêncio | **forte** — teste-guarda de paridade: chave presente em `en` e ausente em `pt-br`/`es` ⇒ CI vermelho |
| Orçamento de arquivos | `.po` + `.mo` por idioma (o `.mo` é binário em PR, ou compila no Docker) | 1 arquivo por idioma, texto puro |

Recomendação: **B**. Estrutura na célula:

```
services/funil/traducoes/
  en.yaml       ← fonte da verdade (o site é inglês por padrão)
  pt-br.yaml
  es.yaml
```

Chaves com namespace **por página** (`cadastro.titulo`,
`cadastro.botao_enviar`, `comum.enviando`), para que "traduzir a página X"
seja um diff pequeno e localizado — vários agentes em paralelo sem conflito de
merge. Template usa `{% t "cadastro.titulo" %}`; a tag recebe o idioma
resolvido da requisição.

O teste-guarda de paridade é o coração da sustentabilidade: **é ele que
transforma "esqueceu de traduzir" de bug silencioso em CI vermelho.** Página
nova = template + chaves novas nos 3 YAML, ou o portão reprova.

### D3 — Idioma é dado do site (`sites.json`), com interim local `[CONSULTA]`

Destino final — a entrada do site declara seus idiomas:

```json
{ "host": "meshcraft.top", "default_language": "en", "languages": ["en", "pt-br", "es"] }
```

…fluindo `sites.json → sincronizar_sites → catalogo → CONV-SITE → request`.
**Porém** isso toca modelo e contrato do catálogo (`contracts/` = Rito de
Contrato, CODEOWNERS — precisa de mandato próprio). Para não travar a fase 1:
**interim declarativo local no funil** (`services/funil/sites_i18n.yaml`,
mapeando host → idiomas), com a promoção ao catálogo registrada como fase 4.
Sites que NÃO estiverem no mapa continuam exatamente como hoje (PT-BR sem
prefixo) — retrocompatibilidade por construção; a landing da operação não muda
em nada.

### D4 — Falta de tradução falha no CI, nunca em produção

Em produção, chave ausente **não** derruba a página (cai para `en` e loga
aviso) — mas essa situação é teoricamente impossível, porque o teste de
paridade (D2) impede o merge que a criaria. Fail-closed no portão, gracioso na
borda: o mesmo desenho do resto da plataforma.

### D5 — SEO desde a primeira página

O `base_mobile.html` do funil passa a emitir, por página:
`<html lang="{{ idioma }}">`, `<link rel="alternate" hreflang="...">` para
cada idioma disponível daquela página, `x-default` apontando para a versão
inglesa, e canonical por idioma. É barato agora e caro de retrofitar depois.

### D6 — Conflito prefixo-de-idioma × prefixo-de-célula: adiado de propósito `[CONSULTA]`

O Traefik roteia por prefixo de caminho (`/quiz`, `/checkout` …). Um caminho
`/pt-br/quiz/...` cairia no funil, não no quiz. **Para o cadastro isso não
importa** (funil serve tudo), mas antes de internacionalizar páginas de outras
células será preciso escolher: idioma DEPOIS do prefixo da célula
(`/checkout/pt-br/...`), regra regex no Traefik, ou funil como proxy. Fica
registrado aqui e perguntado no prompt — decidir barato agora, implementar só
quando precisar.

### D7 — Conteúdo que é DADO (nomes de produto/oferta no catálogo): fase futura `[CONSULTA]`

`site.name`, `product.name` etc. vêm do banco do catálogo. Traduzi-los exige
desenho próprio (tabela de traduções? colunas por locale?) e Rito de Contrato.
A página de cadastro quase não usa esses dados; não bloqueia nada agora.

---

## §3 — A página de cadastro: o que entra já, o que espera o EVO-01

**Fase já:** `/cadastro` (en), `/pt-br/cadastro`, `/es/cadastro` no funil —
formulário nome + e-mail (+ WhatsApp opcional), postando server-side para a
célula `leads` com `source="cadastro-meshcraft"` (o mesmo canal
`POST /leads` que a landing já usa — **zero mudança de contrato**). Isso já
resolve o objetivo imediato do mantenedor: os alunos dos outros sites deixam
nome e e-mail no Meshcraft, com a origem marcada.

**Fase que espera:** transformar cadastro em **identidade** (o aluno entrar,
ter área logada) é exatamente a decisão EVO-01 da Caixa de Sugestões —
proposta de link mágico por e-mail, sem senha. Uma decisão só para as duas
frentes; quando o mantenedor fizer essa conversa, a página troca o destino do
POST e ganha o passo de confirmação. Nada do que a fase 1 constrói é jogado
fora.

---

## §4 — Fases (cada uma = 1 PR dentro do orçamento de 15 arquivos)

| Fase | Entrega | Arquivos (estimativa) | Depende de |
|---|---|---|---|
| **1** | Fundação i18n no funil: resolver de prefixo, `traducoes/{en,pt-br,es}.yaml`, tag `{% t %}`, `sites_i18n.yaml` interim, `base_mobile` com `lang`/hreflang dinâmicos, teste-guarda de paridade + testes de resolução | ~9–11 | respostas da consulta (ou "segue" do mantenedor) |
| **2** | Página `/cadastro` nos 3 idiomas (template + chaves + view + testes), POST para leads com `source="cadastro-meshcraft"` | ~5–7 | fase 1 |
| **3** | **Receita R12 — "página multilíngue"** no `CAMINHO-DOURADO.md`: o passo-a-passo que qualquer agente segue para criar página nova ou idioma novo (idioma novo = 1 arquivo YAML + entrada no mapa do site) | 2–3 (docs) | fases 1–2 provadas no ar |
| **4** | Idioma promovido a dado do catálogo (`sites.json` + modelo + contrato — Rito de Contrato) e aposentadoria do interim | a desenhar | mandato próprio |
| **5** | Conteúdo-dado traduzível (D7) e i18n nas demais células (D6) | a desenhar | necessidade real |

A fase 1 muda a landing atual **apenas** por dentro (a página continua PT-BR,
mesmos textos), porque o site da operação não declara idiomas no interim —
o teste de regressão da landing prova isso.

## §5 — O que precisa do mantenedor · o que NÃO precisa

**Não precisa de nada dele para as fases 1–3:** sem segredo novo, sem console,
sem DNS (o meshcraft.top já está no ar com cadeado — ARMADILHAS §3.18), sem
mudança de contrato congelado, sem Traefik.

**Precisa dele:**
1. **Colar o prompt nas outras IAs** (`PROMPT-CONSULTA-OUTRAS-IAS.md`) e
   trazer as respostas — ou dizer "segue com o recomendado".
2. **A conversa EVO-01** (identidade do aluno), quando quiser — destrava a
   fase de identidade do cadastro E o Lote 1 da Caixa de Sugestões de uma vez.
3. Na fase 4, mandato para o Rito de Contrato do catálogo.
