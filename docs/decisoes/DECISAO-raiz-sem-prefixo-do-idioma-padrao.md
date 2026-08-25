# DECISÃO — o idioma padrão mora na raiz, sem prefixo

> **Decidida pelo mantenedor em 25/08/2026**, em sessão, com estas palavras
> (resumo fiel): *"quero que o site seja todo feito em inglês, mas que ele
> funcione sem o `en` ao lado do nome — não `meshcraft.top/en/`, e sim
> `meshcraft.top` em inglês; no caso dos outros idiomas, sim, precisam ter o
> prefixo."* Este documento registra o que mudou, o que foi revogado, e o custo
> que foi aceito de olhos abertos — para que nenhuma sessão futura "conserte" o
> código de volta lendo o D1 antigo.

**Revoga:** `docs/i18n/PLANO-I18N.md` §2 **D1** na parte "TODOS os idiomas com
prefixo, inclusive o inglês" (23/08/2026). Todo o resto do D1 — e todo o resto
do PLANO-I18N — continua em pé.

## A decisão

**O idioma padrão de um site multilíngue é servido na raiz nua, sem prefixo.
Todo outro idioma leva o seu código.** É regra da plataforma, não configuração
por site: não há campo novo em `contracts/catalogo.openapi.yaml`.

Para o meshcraft.top (`default_language: "en"` em `infra/sites.json`):

| endereço | antes | agora |
|---|---|---|
| `/`, `/cadastro` | 302 → `/en/…` | **200, em inglês** |
| `/pt-br/`, `/es/`, `/pt-br/cadastro` | 200 | 200 — **nada muda** |
| `/en/`, `/en/cadastro`, `/en` | 200 / 302 | **404** |
| `/PT-BR/`, `/pt_br/`, `/EN/` | 404 | 404 — fail-closed, como sempre |
| `/healthz`, `/static/**`, `/sitemap.xml` | 200 | 200 — rota de máquina, não se localiza |

**`/en/…` é 404, não redirecionamento** — decisão explícita do mantenedor na
mesma sessão, perguntado nominalmente. O argumento que a sustenta é o mesmo que
o D1 usou para se justificar em agosto: **não há nada indexado a proteger**, o
meshcraft.top é site de testes. Uma forma canônica por página, sem gêmea.

## Por que o D1 dizia o contrário — e por que o argumento dele perde aqui

O D1 foi decisão unânime das 4 IAs consultadas em 23/08/2026, com dois
argumentos reais:

1. **"Identidade persistente de recurso"**: com prefixo em todos, trocar o
   idioma padrão no futuro é *uma linha de dado*, não migração de 301 em massa.
2. **"Ausência de prefixo também é um idioma"**: uma exceção invisível que
   reapareceria em cada lugar onde um agente gera URL.

Nenhum dos dois é falso. O que mudou é quem decide o trade-off: o argumento 1
otimiza para uma troca de idioma padrão que **ninguém planeja fazer**, cobrando
o preço todo dia, em cada endereço que o dono do projeto digita, compartilha ou
lê num anúncio. O endereço principal de um produto é a coisa mais pública que
ele tem, e `meshcraft.top` é melhor que `meshcraft.top/en/` para o público que
esse site quer — que chega em inglês, de anúncio.

**O custo aceito, escrito para não ser esquecido:** se um dia o
`default_language` do site mudar de `en` para outro idioma, isso **deixa de ser
uma linha de dado** e vira migração de URL de verdade — a raiz passa a servir o
novo idioma e todo endereço em inglês precisa nascer prefixado, com
redirecionamento do que existia. Não é hipotético e não é barato. Foi pago
sabendo.

O argumento 2 continua inteiramente válido, e é por isso que a exceção existe
**num lugar só** no código: `apps/i18n/idiomas.py::caminho_publico()`. Toda URL
pública da célula — canonical, hreflang, x-default, seletor de idioma, sitemap e
link interno — sai dali. Enquanto a regra era incondicional (`/{codigo}{caminho}`)
três cópias dela conviviam sem risco; condicional, cada cópia seria uma chance de
o canonical discordar do link.

## O que a decisão obriga a existir

- **O idioma vence o urlconf.** Com o inglês na raiz nua, o primeiro segmento da
  URL fica ambíguo: `/es` pode ser "espanhol" ou "uma página em inglês chamada
  es". O resolver decide **idioma primeiro**, então uma rota do urlconf chamada
  `es` ou `pt-br` ficaria inalcançável **em silêncio**. Guarda mecânica
  obrigatória: `services/funil/tests/test_d6_roteamento.py` varre o urlconf e
  reprova a colisão — irmão, dentro da célula, do
  `ci/tests/test_rotas_sem_forma_de_locale.py` que já faz isso para o Traefik.
- **`/{padrão}/…` morre antes de qualquer outra regra**, inclusive antes da
  guarda de rota de máquina — senão `/en/healthz` viraria um caminho para a
  sonda (`armadilhas/086`: middleware que reescreve caminho tem DOIS caminhos na
  mesma requisição).
- **Endereços curtos em inglês ficam liberados** (`/faq`, `/api`, `/pro`):
  a antiga `RE_FORMA_DE_IDIOMA` recusava qualquer primeiro segmento com cara de
  idioma — 2-3 letras — mesmo não sendo idioma nenhum. No lugar dela, só recusa
  o que **normaliza** para um idioma habilitado (`/PT-BR/`, `/pt_br/`, `/EN/`).
  `/fr/cadastro` continua 404, agora porque o urlconf não tem a rota — não
  porque uma regex adivinhou.

## O que NÃO mudou

- Sem negociação por `Accept-Language`, em lugar nenhum. **Uma URL = um idioma**
  continua sendo invariante-teste (bytes idênticos com `Accept-Language`
  opostos).
- Caixa e separador continuam fail-closed: só minúsculo com hífen é válido.
- Site **monolíngue** (sem `languages` no catálogo) segue byte-idêntico ao de
  sempre — ele nem entra no resolver de idioma.
- `infra/sites.json` e `contracts/catalogo.openapi.yaml` estão **intocados**:
  `default_language` já era a fonte da verdade e continua sendo.
- Rota de máquina não se localiza, em nenhuma forma.

## Onde isto está escrito

| Documento | O quê |
|---|---|
| **este arquivo** | a decisão, o custo aceito, a origem |
| `docs/i18n/PLANO-I18N.md` §2 D1 | a matriz HTTP nova (a lei operacional) |
| `CAMINHO-DOURADO.md` §R12 | como escrever página multilíngue sob a regra nova |
| `services/funil/apps/i18n/idiomas.py` | `caminho_publico()` — o único lugar que decide prefixo |
| `services/funil/apps/core/middleware.py` | `_com_idioma` — o único lugar que lê prefixo |
