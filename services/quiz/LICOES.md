# LICOES — services/quiz

> Decisões e armadilhas específicas desta célula. Regra geral em `ARMADILHAS.md`.

## Site resolvido LOCALMENTE, não via API do catálogo (desvio deliberado da receita CONV-SITE)

**Contexto:** `CAMINHO-DOURADO.md` §3 define CONV-SITE como uma chamada HTTP a
`CATALOGO_API_URL` para resolver Host→Site, e lista explicitamente quiz entre as
células que usam essa convenção. Um agente lendo só a receita implementaria
exatamente isso — um `CatalogoClient` como o do checkout.

**Por que não foi isso que foi implementado:** `constituicoes/AGENTS.quiz.md` (o
documento mais específico, e por isso mais autoritativo para esta célula) diz
duas coisas que contradizem a chamada de rede:

1. `## Comunicação` → `Consome: nada`.
2. `## Fronteiras` → `SOMENTE LEITURA: contracts/eventos/quiz.completado.v1.json`
   — não lista `contracts/catalogo.openapi.yaml` (checkout e funil listam o seu
   explicitamente, exatamente porque chamam a API do catálogo).

Comparar os três `AGENTS.<celula>.md`: sempre que uma célula chama a API de
outra, isso aparece em **duas** frentes (Fronteiras E Comunicação) — quiz não
tem nenhuma das duas. Isso não parece esquecimento; parece intenção de que o
Crivo seja mesmo "burro" (a missão diz "o quiz não sabe o que é um cartão de
crédito" — a mesma filosofia de isolamento vale para não depender do catálogo
estar de pé).

**O que foi implementado:** `apps.quiz.models.Site` — cadastro **local**
(host, site_id, name), seedado via `seed_quiz` (R9), nunca sincronizado por
rede. `apps/core/middleware.py` consulta esse modelo local em vez de fazer
`httpx.get(.../sites/by-host/...)`. Sem cache de TTL (a receita cacheia para
evitar round-trip de rede repetido; aqui é uma query indexada local, o cache
não paga o preço que paga lá).

**A costura que isso exige do operador:** o `id` do `Site` local **precisa**
ser o mesmo `site_id` que o catálogo usa para aquele host — é assim que
`quiz.completado.v1` correlaciona com o que leads/checkout enxergam do mesmo
lead. Isso é responsabilidade de quem roda `seed_quiz --site-id <id-do-catalogo>`,
não é garantido por código. Não existe hoje verificação automática de que os
dois IDs continuam batendo se o catálogo mudar o ID de um site.

**Se a intenção real era consumir o catálogo:** os dois documentos (receita
genérica vs. constituição da célula) estão em tensão, e resolver isso é
decisão de arquitetura do mantenedor, não deveria ter sido decidida em uma
sessão de feature (Lei 2 do `CAMINHO-DOURADO.md`: "desviar de uma receita não
é improviso local — é issue `arquitetura:` ANTES"). Como o despacho pedia
para seguir em frente, a leitura acima foi registrada aqui e no relatório
final da sessão em vez de travar a entrega — mas **um humano deveria revisar
essa leitura** e, se discordar, abrir a issue e trocar para o `CatalogoClient`
padrão.

## Sem `apps/quiz/__init__.py`

Confirma o que `ARMADILHAS.md` §4.3 já registrava para `management/commands/`:
pacote de namespace (Python 3, sem `__init__.py`) funciona em `INSTALLED_APPS`
também para o pacote raiz do app, não só para `management/commands/`. Usado
aqui para caber no orçamento de arquivos do despacho — não é necessidade
técnica, é economia deliberada.

## Relay do outbox instanciado (despacho quiz/relay-outbox, 22/08/2026)

A dívida "ninguém publica" foi paga: `apps/quiz/tasks.py` espelha o relay de
`pagamentos/core/models.py` (provado em produção) — `relay_outbox()` publica
os pendentes em `eventos.quiz.completado` e SÓ DEPOIS marca `published_at`
(ordem intocável: invertê-la perde evento em silêncio, irmão produtor de
`ARMADILHAS.md` §4.12). O ponto de emissão (`views.formulario`) registra
`transaction.on_commit(relay_apos_commit)` para latência sub-segundo, e
`relay_outbox_periodico` (Huey, `crontab(minute="*")`) é a rede de segurança
que o worker `python manage.py run_huey` executa.

O que aprender aqui, específico desta célula:

- **`settings.HUEY` recebe a INSTÂNCIA de `config/huey.py`, não um dict.**
  `huey.contrib.djhuey` aceita instância pronta; é isso que faz worker e web
  compartilharem o MESMO `TaskRegistry` (sem isso, `run_huey` sobe com o
  registro vazio — `ARMADILHAS.md` §4.11). O teste
  `test_rede_de_seguranca_periodica_registrada_na_instancia_do_huey` guarda o
  fio inteiro mecanicamente.
- **`HUEY_REDIS_URL` NÃO é fail-hard no import** (`os.environ.get` + default
  localhost em `config/huey.py`): o container web importa o módulo via
  INSTALLED_APPS e não pode morrer no boot se a variável faltar em produção.
  `REDIS_STREAMS_URL` é lida no ponto de uso (`apps/quiz/tasks.py`,
  `ARMADILHAS.md` §5.3) pelo mesmo motivo — nada novo entrou no
  `settings.py` como `env()` fail-hard, e o bloco `env:` de
  `.github/workflows/ci-celula.yml` (que já tinha as duas variáveis) não foi
  tocado.
- **Os testes do relay publicam num Redis REAL** (o do CI, serviço `redis:7`;
  local, um container exclusivo do despacho) e validam o envelope QUE CHEGOU
  NO FIO contra `contracts/eventos/quiz.completado.v1.json` — mock de Redis
  aqui seria o §6.9 de novo. E `@pytest.mark.django_db(transaction=True)` é
  obrigatório nos testes de on_commit (§6.5).
- **Produção depende de duas coisas fora deste PR:** (1) o worker
  `quiz-huey` no compose rodando `python manage.py run_huey` (escopo de outro
  despacho do lote); (2) `REDIS_STREAMS_URL` e `HUEY_REDIS_URL` presentes no
  `/opt/plataforma/env/quiz.env` REAL da VPS (o `.exemplo` já as tem; o real
  é do mantenedor conferir).

## Sem contrato REST — só páginas HTML

Diferente de checkout (django-ninja + `contracts/checkout.openapi.yaml`), o
Crivo não expõe API JSON nenhuma: é formulário HTML simples com POST-redirect-GET
(sem Alpine, sem `api.js` — não há necessidade de polling de status como no
Pix). `make contrato-check` já cai no fallback "não expõe contrato congelado"
sem precisar de nenhum ajuste.

## `/healthz` sob prefixo de gateway: Django 5.1 NÃO imuniza contra o §4.10

A tabela de `ARMADILHAS.md` §4.10 diz que no Django 5.1.4 (o desta célula)
`request.path` "funciona" com `FORCE_SCRIPT_NAME` — mas aquela medição foi da
**sonda interna** (`localhost:8000/healthz`, sem prefixo). Pela **borda
pública** o Traefik não remove o prefixo: a requisição chega como
`/quiz/healthz`, e no 5.1 `request.path = scope["path"]` — ou seja, o path COM
prefixo, em qualquer versão do Django. Medido em 22/08/2026:
`https://basileiatoutheou.org/quiz/healthz` → 404, enquanto o healthcheck do
container respondia 200. Isenção de middleware compara **sempre**
`request.path_info` (o path sem o prefixo do gateway), nunca `request.path` —
mesma correção do checkout (PR #65); o guarda daqui é
`tests/test_healthz_script_name.py`, que reproduz o cenário no test client
WSGI (`FORCE_SCRIPT_NAME="/quiz"` faz `client.get("/healthz")` virar
`request.path == "/quiz/healthz"` com `path_info == "/healthz"` — a
reprodução fiel da borda; os asserts de sanidade no teste provam isso).
Detalhe do guarda: `@pytest.mark.django_db` é necessário porque no estado
bugado o middleware consulta o `Site` local — sem a marca, o vermelho seria
erro de acesso a banco em vez do 404 genuíno; e o teste de `/static/` afirma
`django_assert_num_queries(0)` (aqui a resolução é query local, não chamada
ao catálogo — o equivalente do `assert not rota.called` do checkout).

### CORREÇÃO com medição nova (19/09/2026): quem corta o prefixo é o DJANGO

O parágrafo acima está certo no diagnóstico e na cura, mas cala sobre o pedaço
que mais importa, e esse silêncio custou um endereço público errado por quase
um mês. Faltava dizer **quem** tira o prefixo, e quando.

O Traefik de fato não remove nada (`PathPrefix(/quiz)` sem `stripPrefix`). Quem
remove é o Django, dentro do processo, ANTES de casar rota. Lido no
`django/core/handlers/asgi.py` do 5.1.4 instalado nesta célula:

```python
self.script_name = get_script_prefix(scope)   # = settings.FORCE_SCRIPT_NAME
if self.script_name:
    self.path_info = scope["path"].removeprefix(self.script_name)
```

Consequências que a lição antiga não deixava ver:

1. **O roteamento de `/quiz/healthz` SEMPRE casou.** `path_info` chega
   `/healthz` e a rota `path("healthz", ...)` é a mesma de sempre. O 404
   medido em produção nunca foi de roteamento: era a isenção do middleware
   escrita sobre `request.path`, e só isso.
2. **Rota escrita COM o prefixo por dentro casa o endereço DOBRADO.** Enquanto
   o urlconf dizia `path("quiz/<slug>/")`, o único endereço vivo era
   `/quiz/quiz/<slug>/`, e `/quiz/<slug>/` — o que se divulga — respondia 404.
   `reverse()` e o `Location` do POST eram coerentes com a URL dobrada, então
   nada reclamava. Corrigido neste PR; o checkout já tinha passado por isto
   (`services/checkout/config/urls.py`, mesma nota).
3. **Nenhuma suíte via o erro** porque todas mediam o caminho INTERNO, onde os
   dois lados se cancelam. O guarda que fecha isso é
   `tests/test_superficie_publica.py`, e ele precisa de `set_script_prefix`
   (`armadilhas/081`) para que `reverse()` devolva o caminho público.

**A regra prática desta casa, em uma frase:** célula sob `SCRIPT_NAME` escreve o
urlconf SEM o prefixo, compara `path_info` nos middlewares, e monta `Location` e
links com `request.path` / `reverse()`.

## O curinga que o endereço limpo cria (e o 500 que ele quase trouxe)

Tirar o `quiz/` do urlconf põe a página do formulário na RAIZ da célula:
`path("<slug:slug>/", formulario)`. Isso a transforma num curinga de um
segmento, e `/healthz/` e `/static/` passam a casar com ela — justamente os dois
caminhos que `SiteResolutionMiddleware` isenta da resolução de site.

O resultado, sem conserto, seria a view lendo `request.site` que ninguém
definiu: `AttributeError` e 500 onde antes havia 404. A suíte antiga não pegaria
(o teste da sonda afirmava só `status_code != 200`, e 500 passa nisso).

O conserto mora na view, num arquivo só: `_quiz_do_site` lê o site com `getattr`
(o atributo é legitimamente ausente nos caminhos isentos, e quem documenta isso
é o próprio middleware) e devolve 404 quando ele não veio. Guarda:
`test_caminhos_isentos_de_site_nao_viram_500_no_curinga`.

Efeito colateral aceito: `BarraNoFinal` deixou de agir sobre caminhos de um
segmento só (eles resolvem agora, e a regra 1 o barra). O que ele ainda conserta
é o caminho de dois segmentos, `/quiz/<slug>/resultado/`, que é exatamente o
link que as pessoas copiam.

### O segundo efeito: um slug pode nascer publicado e inalcançável

Achado na revisão do PR. O mesmo curinga faz com que um quiz de slug `healthz`
more em `/healthz/`, caia na isenção de resolução de site e responda 404 para
sempre: publicado, inalcançável, e sem nada acusando na hora de semear.
`seed_quiz` passa a recusar esses slugs, e a lista ele LÊ de `CAMINHOS_SEM_SITE`.

**Ler a lista não é preciosismo, e a medição provou isso contra mim.** A
comparação do middleware é `startswith`, então a isenção é mais larga do que os
dois nomes sugerem: `healthz2` e `healthzinho` também começam por `/healthz` e
também seriam isentos. A primeira versão do teste listava `healthzinho` como
slug honesto, e foi o próprio código, ao recusá-lo, que corrigiu o teste. Uma
conferência escrita à mão (`slug in ("healthz", "static")`) erraria essa borda
exatamente como eu errei, e a sabotagem que reproduz isso está medida no PR.

### E um teste que se autoconfirmava

Também da revisão. O guarda do alcance do cookie de CSRF fazia
`settings.CSRF_COOKIE_PATH = "/quiz"` e depois conferia que o cookie saía em
`/quiz`: media se o Django obedece a configuração que o próprio teste acabou de
escrever. Trocar a linha do `config/settings.py` por `CSRF_COOKIE_PATH = "/"`
fixo deixava o teste VERDE.

A causa é que `CSRF_COOKIE_PATH = FORCE_SCRIPT_NAME or "/"` é calculado UMA vez,
no import. Trocar `settings.FORCE_SCRIPT_NAME` em tempo de execução (o que a
fixture `env_de_producao` faz, e é o certo para o resto do arquivo) não
recalcula nada.

**Valor derivado de outro no import do settings não se testa por `settings`
sobrescrito: exercite o IMPORT**, com a variável de ambiente real, que é o que a
fixture `settings_recarregavel` faz. Vale para qualquer célula desta casa que
derive cookie, caminho ou URL do `SCRIPT_NAME`.

## O botão da tela de resultado: destino é ARGUMENTO do seed, não constante

A tela de resultado era um beco sem saída. O botão agora é da faixa
(`ResultBand.botao_destino` e `.botao_rotulo`), e o `seed_quiz` exige
`--destino-do-botao`.

**Por que argumento, e não uma constante `/checkout/<oferta>/` no código:** o
Crivo não sabe o que é um checkout (`AGENTS.quiz.md` → "Consome: nada"), e a
oferta é dado de CADA site — o mesmo seed roda em meshcraft.top e
basileiatoutheou.org, e quem sabe qual é a oferta de cada um é o catálogo, que
esta célula não consulta. Guardar o endereço como dado opaco mantém a fronteira
de pé e ainda serve para um destino que não seja checkout.

**O que foi medido antes de decidir** (leitura de fatos públicos da plataforma,
não dependência nova): o checkout publica a oferta em `path("<slug:offer_slug>/",
...)` sob o router Traefik `PathPrefix(/checkout)`, que casa por CAMINHO em
qualquer host da VPS. Logo um caminho RELATIVO como `/checkout/curso-teste/`
vale em qualquer site sem esta célula saber por quê, e é esse o valor usual do
argumento. A oferta padrão de cada site está em `infra/sites.json`
(`default_offer_slug`) — hoje só `meshcraft.top`, com `curso-teste`.

**Por que o argumento é obrigatório:** destino ausente é tela sem botão, que é o
beco que este trabalho veio fechar. Falhar alto na hora de semear é melhor que
publicar um funil mudo.

**Por que as faixas passaram a `update_or_create`:** todo banco semeado antes
deste PR já tem as três faixas, sem botão. `get_or_create` acharia a linha, não
escreveria nada, imprimiria "✅" e deixaria o beco de pé para sempre. Guarda:
`test_o_seed_poe_botao_em_faixa_que_ja_existia_sem_ele`.

**Nomes em português no meio de um modelo em inglês** (`botao_destino` ao lado
de `min_score`): escolha do despacho, pedida no brief. O modelo fica misto e
isso é dívida declarada, não descuido.

## CSRF: o token era decoração (corrigido em 19/09/2026)

`formulario.html` emitia `{% csrf_token %}` desde o primeiro dia, e
`settings.MIDDLEWARE` não tinha `CsrfViewMiddleware`. Qualquer página da
internet podia mandar POST para `/quiz/<slug>/` e gravar `Submission` com e-mail
e telefone escolhidos por quem publicou o formulário — e disparar
`quiz.completado.v1` por lead que nunca existiu. Era a única célula pública da
casa nessa situação.

Duas coisas que a correção ensina, e valem para qualquer célula sob Traefik:

- **`CSRF_TRUSTED_ORIGINS` não é necessário** e não entrou. Ele serve para
  aceitar origens DIFERENTES do host da requisição; aqui formulário e POST são
  sempre do mesmo host (Lei 9: um deploy, N domínios, cada um falando consigo
  mesmo). Nenhuma das outras nove células com CSRF desta casa usa a lista.
- **`SECURE_PROXY_SSL_HEADER` é**, e sem ele NENHUM envio honesto passaria. O
  TLS termina no Traefik, o uvicorn vê `http`, o navegador manda
  `Origin: https://<site>` e o Django compara com
  `"%s://%s" % (request.scheme, request.get_host())`. Sem o header a comparação
  é contra `http://<site>` e todo POST legítimo vira 403 — em produção, e só em
  produção. Não custa variável de ambiente nova: o Traefik sempre emite
  `X-Forwarded-Proto`. Guarda:
  `test_https_atras_do_traefik_aceita_a_origem_do_proprio_site`.

E o cookie tem nome próprio (`quiz_csrf`), com `CSRF_COOKIE_PATH` no prefixo da
célula: num único domínio moram várias células sob prefixos, e duas publicando
`csrftoken` deixam qual delas o servidor lê na mão da precedência por caminho.

Detalhe de teste que não é opcional: o `client` do pytest-django nasce com
`enforce_csrf_checks=False`. Um teste de CSRF escrito com ele passa de verde com
o middleware DESLIGADO. O arquivo `tests/test_superficie_publica.py` usa
`Client(enforce_csrf_checks=True)` por isso.
