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
**RESOLVIDA no despacho funil/i18n-cadastro (decisão da maestro):** todo POST
de site registrado vai para a PRÓPRIA URL prefixada — a ilha da landing posta
em `{% url_i18n 'capturar_lead' %}` (`/{idioma}/leads`) e o form de cadastro
em `{% url_i18n 'cadastro' %}`; caminho nu segue 404. `/leads` NÃO virou rota
de máquina.

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

## Lint de template por regex também lê os COMENTÁRIOS do template

**Sintoma:** `pytest` morre na inicialização da sessão inteira com
`ImproperlyConfigured: [i18n] catálogo inválido — célula não sobe`, apontando
um template que parece correto — a violação citada (a tag `url` crua) só
existe dentro de um comentário HTML que explicava a própria regra.
**Causa:** os lints do validador (`RE_USO_T`, `RE_URL_CRU`) varrem o ARQUIVO
inteiro por regex; comentário HTML é texto como qualquer outro. E como o
validador roda no BOOT (D4 fail-closed), a "violação" documentada derruba o
`django.setup()` do pytest antes de qualquer teste ser coletado.
**Solução:** em comentário de template, descreva a tag pelo NOME ("a tag url
crua do Django"), nunca pela sintaxe literal. Vale para qualquer lint novo.
**Origem:** despacho funil/i18n-cadastro — o comentário de cabeçalho de
`templates/funil/cadastro.html`.

## `hreflang="es"` continua aparecendo na página noindex — mas só na âncora do seletor

**Sintoma:** asserção de "es fora do hreflang" escrita como
`'hreflang="es"' not in html` falha mesmo com a emissão SEO correta.
**Causa:** o seletor de idiomas emite `<a ... hreflang="es">` de propósito —
seletor é para gente; o hreflang de robô é a tag `<link rel="alternate">`.
**Solução:** a asserção negativa mira `'<link rel="alternate" hreflang="es"'`
(mesmo padrão do teste da fase 1), nunca o atributo solto.
**Origem:** despacho funil/i18n-cadastro — `tests/test_cadastro.py`.

## Erro de form localizado se afirma com `override()`+`gettext`, nunca com string estrangeira colada

O `activate()` do resolver faz o Django traduzir sozinho as mensagens de erro
de formulário. No teste, o valor esperado sai do próprio catálogo do Django
(`with override("es"): esperado = gettext("This field is required.")`) — se a
versão do Django mudar a frase, o teste continua medindo a coisa certa (a
LOCALIZAÇÃO), em vez de quebrar por copy desatualizado dentro do teste.
**Origem:** despacho funil/i18n-cadastro — `tests/test_cadastro.py`.

## Link cross-célula em página multilíngue NÃO ganha prefixo de idioma (por enquanto)

A landing i18n continua linkando `/checkout/<slug>/` SEM prefixo: o gateway
não tem a regra locale-first do D6, então `/en/checkout/...` cairia no funil
(catch-all do Traefik), o resolver decaparia o idioma e o path morreria 404
dentro DESTA célula. Regra prática: link interno da célula = `{% url_i18n %}`
(obrigatório — lint no validador reprova a tag `url` crua em template i18n);
link para OUTRA célula = cru e monolíngue, até a mecânica do D6 entrar no
Traefik. Quando a primeira página de outra célula se internacionalizar, este é
o lugar a revisar (pendência já registrada no PLANO-I18N D6).
**Origem:** despacho funil/i18n-cadastro — `templates/funil/landing_i18n.html`.

## `_juridico: true` sem aspas nunca chega ao portão do D8.2 — morre antes, no loader

**Sintoma:** você escreve `_juridico: true` exatamente como o PLANO-I18N D8.2
manda, e a mensagem que volta não fala de revisão humana nenhuma: é
`folha True não é string (bool) — escreva o valor entre aspas`.
**Causa:** a regra "toda folha é `str`" do loader estrito (D2.7) roda ANTES de
qualquer regra semântica, e `true` em YAML é booleano. O portão jurídico nem
chegou a ser consultado.
**Solução:** no catálogo escreve-se **`_juridico: "true"`**, com aspas — e o
validador só aceita esse literal. Não existe `"false"`: a **ausência** da chave
é a forma de dizer "não é jurídico"; um valor que desligasse o portão seria o
silenciador barato (mesmo espírito da regra anti-burla do `_fonte`). Vale para
qualquer meta booleana futura do catálogo.
**Origem:** despacho funil/i18n-juridico — `apps/i18n/catalogo.py`.

## A revisão humana do texto jurídico é declarada POR IDIOMA, e expira no diff

`_revisado_humano` é um **mapa idioma → "Quem revisou AAAA-MM-DD"**, nunca uma
string única da chave. Duas razões, as duas mecânicas:

1. **Por idioma** porque revisar o inglês não valida o espanhol — uma
   declaração agregada faria uma leitura responder por textos que o revisor
   nunca viu, exatamente a responsabilidade que o D8.2 existe para evitar.
   Declaração para idioma que a chave não tem reprova (órfã), e
   `_revisado_humano` sem `_juridico` também.
2. **Expira no diff** (`_revisao_no_diff`, mesma mecânica do anti-burla do
   `_fonte`): se o valor de um idioma mudou contra `${BASE_REF:-origin/main}` e
   a declaração daquele idioma NÃO mudou, reprova. Sem isso, a declaração seria
   carimbo perpétuo (ARMADILHAS §5.15).

A data ISO é obrigatória no valor: sem "quando", "revisado" é inverificável.
Auditar tudo isso é um grep — `grep -rn "_revisado_humano" services/*/traducoes/`.
E o portão é fail-closed nas duas entradas: texto jurídico sem revisão reprova
no `make ci` **e o boot recusa subir** (`ImproperlyConfigured`, D4). Também
por isso `_juridico` com `_fonte: pendente` reprova — texto com efeito legal não
vai ao ar em estado degradado, senão o fallback publica o inglês numa página
que se apresenta traduzida.
**Origem:** despacho funil/i18n-juridico — `apps/i18n/validador.py`,
`tests/test_i18n_juridico.py`.

## Guarda de comprimento (D8.3) é RELATÓRIO — e precisa de piso, senão vira ruído

`Resultado.avisos` carrega os avisos de razão de comprimento (>3× ou <0,3× do
`en`); eles **não** mudam o estado PASS/FAIL, sobem como WARNING no boot e
aparecem no `make ci` pelo sumário de warnings do pytest
(`test_relatorio_de_comprimento_da_celula_real`). O piso de 12 caracteres no
`en` não é enfeite: `"E-mail"` → `"Correo electrónico"` já é 3× e está CERTO —
sem o piso, o relatório nasceria com falso positivo no catálogo real, e
relatório barulhento é relatório ignorado. Reprovar por comprimento também
estava fora de questão: idioma legitimamente prolixo existe, e o D8.3 diz
RELATÓRIO, não portão.
**Origem:** despacho funil/i18n-juridico — `apps/i18n/validador.py`.

## Teste novo do i18n reusa os helpers de `test_i18n_catalogo`, não um mundo próprio

`tests/test_i18n_juridico.py` importa `_celula`, `_doc_ok`, `_git`,
`TEMPLATE_OK` e `RAIZ_REAL` de `test_i18n_catalogo` (import pelo nome do
módulo, sem `tests.` — a pasta não é pacote e o pytest a põe no `sys.path`).
A regra que isso protege: **regra nova não pode precisar de uma célula de
mentira própria para passar** — se ela só fecha num mundo feito sob medida,
não está medindo a célula. Cuidado prático ao montar chave jurídica de teste: o
glossário continua valendo, então `Meshcraft` no `en` obriga `Meshcraft`
literal no pt-br e no es.
**Origem:** despacho funil/i18n-juridico.

## Onde mora cada pedaço do i18n depois que o idioma virou dado do catálogo (fase 4)

O interim `sites_i18n.yaml` declarava CINCO coisas juntas; o contrato do
catálogo (schema `Site`) só recebeu DUAS. As outras três não podiam sumir, e
espalhá-las seria pior que o interim. Onde cada uma foi parar, e por quê:

| coisa | onde vive agora | por quê |
|---|---|---|
| quais idiomas o site serve (`code`) | **catálogo** (`languages[]`) | é dado do SITE — muda por site, sem deploy |
| `indexable` por idioma | **catálogo** (`languages[].indexable`) | idem: flipar um dado indexa o `es` |
| tag BCP 47 (`pt-br`→`pt-BR`) e `dir` | `apps/i18n/idiomas.py`, **derivados do código** | propriedade do IDIOMA, igual em todo site: como dado por site seriam N lugares para escrever a mesma verdade, e N para escrevê-la errado (`dir: rtl` num site em inglês passaria pelo contrato) |
| glossário de não-traduzir (D8.1) | `catalogo.py` → `GLOSSARIO` | política de TRADUÇÃO da célula; quem precisa da regra é quem escreve a tradução, e o validador a lê de lá |
| cadeia de fallback de variante (D4) | `catalogo.py` → `VARIANTES` | idem: dois sites servindo `pt-pt` caem no mesmo `pt-br` porque o TEXTO é o mesmo, não porque cada um configurou isso |

Regra de bolso que sobrou: **o contrato carrega o que varia por site; a célula
carrega o que varia por idioma ou por catálogo de tradução.** Antes de propor
campo novo no contrato do catálogo, pergunte se dois sites poderiam querer
valores diferentes — se não poderiam, o campo é da célula.
**Origem:** despacho funil/idioma-do-catalogo (fase 4).

## Idioma que o catálogo declara e a célula não sabe renderizar é IGNORADO, não servido

`idiomas_do_site()` cruza o `languages` do catálogo com o que a célula sabe
renderizar (`cat.IDIOMAS_BASE` + `cat.VARIANTES`). Idioma de fora — um `fr`
adicionado ao site antes das traduções — **não vira URL**: sai da lista com um
ERROR no log. Servir `/fr/` cairia inteiro no fallback para o inglês, ou seja,
publicar uma URL francesa com página inglesa: exatamente o padrão que o D5
manda evitar. Consequência prática para quem lançar idioma novo: **traduções
primeiro** (`IDIOMAS_BASE` + `traducoes/*.yaml`, com o validador verde), **o
dado do site depois** — a ordem inversa não quebra nada, só não faz efeito.
**Origem:** despacho funil/idioma-do-catalogo — `apps/i18n/idiomas.py`.

## Rota isenta do CONV-SITE não tem `request.site` — e a isenção envelhece

**Sintoma:** o `/sitemap.xml` estava em `CAMINHOS_SEM_SITE` ("não depende do
catálogo, como o `/healthz`") e tinha até um teste provando isso. Quando os
idiomas passaram a vir do catálogo, essa isenção virou um beco: sem
`request.site` não há `languages`, e o sitemap não tinha como saber quais URLs
listar.
**Causa:** a isenção fora escrita em função da ROTA ("é rota de máquina"), mas
o que a decide é o DADO de que a rota precisa. O dado migrou; a isenção não.
**Solução:** dividir em duas listas — `CAMINHOS_SEM_SITE` (`/healthz`,
`/static/`: sonda e estáticos, que não podem depender do catálogo estar de pé)
e `CAMINHOS_DE_MAQUINA` (`/sitemap.xml`: resolve o Site normalmente, com o
mesmo cache de 60s, mas **nunca se localiza** — nenhum prefixo, nenhum redirect
da matriz D1). De brinde, o sitemap passou a usar o host canônico do Site em
vez de `request.get_host()`, como o canonical já fazia (D5).
**Preço, declarado:** o sitemap deixou de ser servível com o catálogo fora do
ar. Se um dia isso doer, a saída é cache, não isenção.
**Origem:** despacho funil/idioma-do-catalogo — `apps/core/middleware.py`,
`apps/core/views.py`.

## Dado de site que a célula não entende: degradar para monolíngue, nunca adivinhar

Três casos de `Site` malformado, e a decisão de cada um (todos com ERROR no
logger `funil.i18n`, nunca em silêncio):

- **`languages` ausente/vazio** ⇒ monolíngue, SEM alarme: é o contrato dizendo
  "site de um idioma só". É também a degradação da fase 4 — enquanto o catálogo
  não servir os campos, o site multilíngue volta a ser o de antes, byte a byte.
- **`default_language` ausente ou fora da lista** ⇒ monolíngue COM alarme.
  Eleger "o primeiro da lista" seria o site-padrão silencioso que o [INV-P11]
  proíbe, e mandaria a raiz redirecionar para um idioma que ninguém escolheu.
- **`indexable` não-booleano** (`"false"` string, p.ex.) ⇒ **noindex** com
  alarme. Fail-closed pelo lado barato: indexar por engano custa caro e demora
  a reverter; não indexar custa tráfego e reverte flipando um dado.

O alarme sai UMA vez por janela de cache (60s), não por requisição: o
`idiomas_do_site()` roda no `_resolver` do middleware, junto com a resolução do
Site, e o resultado é cacheado com ele. Dado inválido não vira enxurrada de log.
**Origem:** despacho funil/idioma-do-catalogo — `apps/i18n/idiomas.py`,
`apps/core/middleware.py`.

## Fixture de teste especializa o mock do conftest re-registrando a MESMA rota

Com o idioma vindo do catálogo, o "site multilíngue" dos testes nasce do mock:
a fixture `com_i18n` faz `rede.get(f"{CATALOGO}/sites/by-host/{HOST_A}").mock(...)`
sobre uma rota que o `conftest` já tinha registrado. Isso **substitui** a rota
anterior — é comportamento documentado do respx (`Router.add`: "replacing any
existing route with same name or pattern"), não sorte de ordenação. É o que
permite ter, no mesmo arquivo, testes multilíngues e a regressão monolíngue
byte-idêntica sobre o MESMO host, sem inventar um terceiro domínio.
**Origem:** despacho funil/idioma-do-catalogo — `tests/test_i18n_http.py`.

## `CAMINHOS_SEM_SITE` casa o `path_info` CRU — `/pt-br/healthz` respondia 200

> ✅ **RESOLVIDO em 24/08/2026.** A lição fica porque a CAUSA continua valendo
> para a próxima rota de máquina que a célula servir: o que mudou é que agora
> existe mecanismo, e não só vigilância.

**Sintoma:** o D6 do PLANO-I18N afirma que rota de máquina nunca se localiza e
que "o desenho atual já obedece por construção". Medido em 24/08/2026, no
meshcraft: `/pt-br/api/...` 404, `/pt-br/webhooks/...` 404, `/pt-br/sitemap.xml`
404 — e **`/pt-br/healthz` 200**, com o JSON da sonda.
**Causa:** a isenção do `SiteResolutionMiddleware` roda ANTES de tudo, contra o
`path_info` como ele chega (`/pt-br/healthz`.startswith(`/healthz`) é False).
Não sendo isenta, a requisição segue para `_com_idioma()`, que decapa o prefixo
e devolve `path_info = "/healthz"` ao urlconf — que resolve a view normalmente.
O `/sitemap.xml` escapa por acidente feliz: a VIEW dele tem guarda própria
(`request.path != "/sitemap.xml"` ⇒ 404). O `/api/**` e o `/webhooks/**` escapam
porque o funil não serve rota nenhuma nesses prefixos — quem serve são outras
células, e lá o Traefik nem chega a casar a rota prefixada.
**Regra que sobra:** *toda rota de máquina que a PRÓPRIA célula serve ganha uma
gêmea localizada de graça*, a menos que esteja em `CAMINHOS_DE_MAQUINA` ou que a
view se defenda sozinha. A isenção protege o caminho nu; ela não protege a
forma prefixada.
**Solução (aplicada em 24/08/2026):** o middleware confere `ROTAS_DE_MAQUINA` —
a união de `CAMINHOS_SEM_SITE` e `CAMINHOS_DE_MAQUINA` — também **depois** de
decapar o prefixo, dentro do `_com_idioma()`. É o único ponto do fluxo em que dá
para ver que `/pt-br/healthz` **é** a rota de máquina `/healthz`: antes dali o
caminho ainda está cru, depois dali o urlconf já resolveu. Uma guarda, as três
rotas cobertas (`/healthz`, `/static/**`, `/sitemap.xml`) e as próximas de
graça — quem entrar nas listas fica protegido nas duas formas, nua e prefixada.
**O que impede a REINCIDÊNCIA (a classe, não o caso):** o
`test_toda_rota_do_urlconf_e_classificada_maquina_ou_localizavel` obriga toda
rota do `config/urls.py` a estar declarada como de máquina (nas listas do
middleware) ou como página (em `ROTAS_LOCALIZAVEIS`, no próprio teste). Rota
nova sem classificação fica vermelha, e a pergunta "esta se localiza?" é feita
na hora de criá-la, não meses depois por medição. A guarda cura o caso; este
teste cura a classe.
**O que o `xfail(strict=True)` provou:** ele foi escrito para ficar vermelho por
XPASS no dia do conserto, e foi exatamente assim que o conserto se anunciou — o
marcador e o teste que afirmava o 200 saíram na mesma edição, sem sobrar teste
mentindo. Desvio registrado com alarme de conserto vale mais que desvio
consertado sem registro.
**Origem:** despacho funil/guardas-d6 (o achado) e funil/desvio-d6-healthz (o
conserto, 24/08/2026) — `apps/core/middleware.py`, `tests/test_d6_roteamento.py`.

## Guarda cuja violação nasce em `infra/` não pode morar em `services/<celula>/tests/`

**Sintoma:** o guarda 1 do D6 ("nenhum prefixo de rota de célula pode ter forma
de locale") parece teste de célula — mas o arquivo que ele vigia é
`infra/traefik/dynamic/plataforma.yml`.
**Causa:** o `ci-celula.yml` roda o `make ci` de uma célula SOMENTE quando o
diff tem `services/<celula>/…` (`ci/ci.py::celulas_tocadas` conta exatamente
isso; lista vazia ⇒ o job `rodar` é pulado e o gate aceita como SKIP legítimo).
Um PR que acrescenta `PathPrefix('/pt')` ao Traefik toca ZERO células — a
suíte do funil nunca rodaria. O guarda seria decoração exatamente no PR para o
qual foi escrito.
**Solução:** guardas de plataforma vão para `ci/tests/`, que o workflow
`muralhas` roda em TODO PR (`ci/ci.py --apenas testador`). Bônus: só de lá se
enxergam as DUAS pontas de uma colisão de roteamento — a tabela de rotas e o
`infra/sites.json` que declara os idiomas. Nenhuma célula pode ler as duas.
**Pergunta de bolso antes de escrever teste-guarda:** *qual diff introduziria a
violação que estou tentando pegar?* Se esse diff não toca a célula, o teste não
é da célula.
**Origem:** despacho funil/guardas-d6 — `ci/tests/test_rotas_sem_forma_de_locale.py`.

## Guarda de FORMA erra dos dois lados; cruze com o DADO real

**Sintoma:** a regra do D6 é "prefixo de rota não pode ter forma de locale
(2-3 letras ± região)". Escrita ao pé da letra, ela reprova `/api/checkout`
(`api` são 3 letras minúsculas — casa a forma por acidente de comprimento) e
deixa passar `/zh-hant-tw` (longo demais para a forma, e ainda assim um idioma
perfeitamente declarável).
**Solução:** duas regras, e as duas precisam passar. (A) FORMA, com os
namespaces de máquina que o próprio D6 reservou (`api`, `webhooks`, `static`,
`healthz`) isentos — é a rede para idiomas que ninguém declarou ainda. (B)
COLISÃO com os `code`/`default_language` realmente declarados em
`infra/sites.json` — é a que pega o caso de hoje, cresce sozinha a cada idioma
novo, e **fecha a válvula da regra A**: se um dia alguém declarasse o idioma
`api`, a isenção de máquina deixaria de servir de esconderijo.
**Generalização:** heurística de forma é ótima para o futuro e péssima para o
presente; o cruzamento com o dado é o contrário. Guarda bom tem os dois, e a
isenção de um nunca é isenção do outro.
**Origem:** despacho funil/guardas-d6 — `ci/tests/test_rotas_sem_forma_de_locale.py`.

## A isenção de `/static/` no CONV-SITE não era uma rota — e por 3 dias não houve nenhuma

**Sintoma:** `/static/funil/api.js` respondia **404 em produção** nos dois domínios
(medido em 24/08/2026), enquanto `/healthz` respondia 200 no mesmo host. As duas
landings carregam esse `<script>` e a ilha Alpine chama `api.post(...)` logo abaixo:
o formulário "Quero receber novidades" estava morto no navegador, sem erro visível
para o visitante e sem uma linha vermelha em lugar nenhum.
**Causa:** `CAMINHOS_SEM_SITE = ("/healthz", "/static/")` no middleware faz o que diz
— entrega a requisição ao urlconf sem resolver Host. Só que o urlconf **não tinha
rota de estático**, e com `DEBUG=0` o Django não serve nada por conta própria. A
isenção parecia a solução inteira porque ela é metade dela; a outra metade nunca foi
escrita. Foi por isso que `test_d6_roteamento` ficou verde o tempo todo: ele mede a
isenção com um **espião no lugar da view** — ou seja, tudo menos a resposta HTTP.
**Solução:** `apps/core/views.py::servir_estatico` + `re_path(r"^static/...")` no
urlconf, servindo de `STATICFILES_DIRS[0]` (o diretório-fonte). O mecanismo completo
— inclusive por que `STATIC_ROOT` está VAZIO na imagem e por que whitenoise não
resolveria — está em `armadilhas/083-static-404-em-producao-com-todos-os-settings.md`.
**Regra que sobra para esta célula:** isenção de middleware nunca é rota. Toda vez
que um caminho entrar em `CAMINHOS_SEM_SITE` ou `CAMINHOS_DE_MAQUINA`, pergunte quem
responde por ele no `config/urls.py` — se a resposta for "ninguém", o caminho está
isento de tudo, inclusive de existir.
**Origem:** despacho funil/static-em-producao — `apps/core/views.py`,
`config/urls.py`, `tests/test_static_em_producao.py`.

## Rota nova nesta célula precisa passar pela matriz de idioma ANTES de existir

O resolver reescreve `request.path_info` (`/pt-br/static/x.js` → `/static/x.js`)
antes da resolução de URL. Consequência prática que pegou a rota de estático em
cheio: **toda rota nova nasce alcançável por `/{idioma}/<rota>`**, de graça e sem
ninguém pedir. Para página, isso é o recurso funcionando. Para rota de MÁQUINA
(`/healthz`, `/static/**`, `/sitemap.xml`) é regressão: publica uma URL por idioma
para o mesmo byte, que é exatamente o que o guarda 2 do D6 proíbe — e o
`test_rota_de_maquina_prefixada_nao_vira_rota_localizada` teria ficado **vermelho**
se a rota de estático entrasse sem a guarda. A guarda é uma linha, a mesma do
`sitemap_xml`:

```python
if getattr(request, "idioma", None) is not None:
    raise Http404("<rota> não tem prefixo de idioma")
```

Checklist de rota nova aqui: é de gente ou de máquina? Se for de máquina, a guarda
entra junto com a rota, no mesmo commit — depois, o vermelho vem do guarda alheio e
custa uma rodada para entender de onde veio.
**Origem:** despacho funil/static-em-producao — `apps/core/views.py`.
