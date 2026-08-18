# LIÇÕES — célula pagamentos

Documento vivo, versionado (NÃO é `arquivos/painel-*.html` — aquele é local/gitignored
e é território da janela raiz). Objetivo: qualquer agente que abrir uma sessão dentro
de `services/pagamentos/` (esta ou futuras — 3b webhooks, congelamento, manutenção)
lê isto em 1 minuto e não perde tempo redescobrindo o que segue. Ao encontrar algo
novo que economizaria tempo do próximo agente, acrescente aqui (seção "Sessões"),
não reescreva o que já está registrado. Se algo aqui empacar tempo de um agente em vez
de economizar, corrija ou apague — o documento serve à velocidade, não a si mesmo.

## Ambiente local (Windows, esta máquina) — visto no Prompt 2 (catalogo) e confirmado aqui

- `python3` é um stub quebrado (Microsoft Store) — use `python` sempre.
- `make` não existe neste Git Bash — rode os alvos do Makefile na mão (comandos
  exatos na seção "Comandos" abaixo).
- `ci/freeze-de-contrato.sh` chama `python3` internamente — localmente ele dá
  falso-positivo "OK" (os dois lados do diff falham igual e "batem"). Valide o
  contrato manualmente: `python manage.py export_openapi` + comparar com
  `yaml.safe_load` + `json.dumps(..., sort_keys=True)` dos dois lados.
- `PYTHONUTF8=1` evita `UnicodeEncodeError` em output com emoji/acento (cp1252).
- **Novo nesta sessão:** `/tmp/...` dentro do Bash tool (Git Bash/MSYS) NÃO é
  gravável/resolvível de forma confiável para uso cruzado bash→python neste setup —
  um arquivo escrito com `> /tmp/x.json` no bash não foi encontrado por
  `open("/tmp/x.json")` no Python nativo do Windows chamado em seguida. Use o
  diretório de scratchpad da sessão (caminho absoluto Windows) para qualquer
  arquivo intermediário que precise ser lido de volta por um processo Python.
- **Novo nesta sessão:** o `python.exe` nativo do Windows (não é o Python do
  Git Bash/MSYS) NÃO entende paths estilo `/c/Users/...` quando o path é um
  literal de string dentro do código (heredoc, argumento de `open()` etc.) —
  só funciona quando é o próprio SO resolvendo o cwd do processo (paths
  relativos) ou quando o Bash faz a conversão automática de argv para um
  executável reconhecido. Para qualquer path absoluto usado DENTRO de um
  script Python, escreva estilo Windows com barra normal:
  `C:/Users/.../arquivo.json` (Python aceita `/` como separador no Windows).
- Docker Desktop: subir só o serviço `db` é suficiente para rodar testes locais
  sem subir a célula inteira: `docker compose -f docker-compose.dev.yml up -d db`.
- **Atualização (2026-08-18, mesma sessão):** o usuário instalou `make` via
  WinGet (`GNU Make 4.4.1`) — mas isso foi no PowerShell dele; o Git Bash deste
  Bash tool tem PATH separado e não vê o binário por padrão. Funciona se você
  prefixar o PATH manualmente NO MESMO comando (estado de shell não persiste
  entre chamadas do Bash tool):
  `export PATH="/c/Users/lawfe/AppData/Local/Microsoft/WinGet/Packages/ezwinports.make_Microsoft.Winget.Source_8wekyb3d8bbwe/bin:$PATH" && make ci`.
  Mesmo com `make` funcionando, `make contrato-check` ainda chama `python3`
  internamente (Makefile usa `python manage.py export_openapi` mas
  `ci/freeze-de-contrato.sh` shellado por ele usa `python3`) — o
  falso-positivo local persiste; siga validando o contrato manualmente.
- Ambiente Python isolado: crie um venv FORA do worktree (ex.: no scratchpad da
  sessão) — evita risco de `git add` acidental de um `.venv/` sem entrada no
  `.gitignore` desta célula (o `.gitignore` daqui não lista `.venv/`).
- `.env.dev` (gitignored) com as chaves mínimas para rodar tudo localmente:
  `DJANGO_SECRET_KEY`, `DEBUG=0`, `DATABASE_URL` (postgres local do compose),
  `TOKENS_ACEITOS_CHECKOUT`, `MP_ACCESS_TOKEN` (formato `TEST-...` — NUNCA
  `APP_USR-`, nem em teste local — INV-P8).

## Comandos (equivalente manual de `make ci`, nesta máquina)

```bash
set -a && source .env.dev && set +a
python -m black --check .
./.venv-ou-scratchpad/Scripts/lint-imports.exe        # roda mesmo sem 'make'
python -m mypy .
python -m pytest -q
python manage.py export_openapi > <scratch>/vivo.json # depois comparar manualmente
```

## Decisões de arquitetura desta sessão (Prompt 3a — intents)

- `core/models.py` é o ÚNICO app Django com `models.py`/migrations na célula
  nesta fase: o modelo `Intent` mora em `core` (é o que a Constituição da
  célula descreve como dono de "modelos, ledger, outbox"). `methods/pix` e
  `methods/card` são pacotes Python puros (sem `models.py`, sem
  `migrations/`, sem entrada em `INSTALLED_APPS`) — leem/escrevem `Intent`
  importando `pagamentos.core.models`, o que é permitido (a independência do
  INV-P9 é só ENTRE os dois métodos, e entre método e `providers`, nunca
  entre método e `core`). Isso evita duplicar app Django (e o
  `migrations/__init__.py` obrigatório) por método — economiza arquivos no
  orçamento sem violar nenhum invariante.
- `core/gateway.py` expõe funções (não uma classe) que `methods/pix` e
  `methods/card` chamam; internamente importa `providers.mercadopago.client`.
  É a única costura permitida entre método e provider (INV-P9, contrato
  `metodos-so-falam-com-core` do `.importlinter`, já existente no esqueleto —
  não precisou editar `.importlinter`).
- `api/intents.py` NÃO usa `ninja.Schema` para o corpo da requisição nem para
  a resposta (o esqueleto já vinha assim, comentário explica por quê: evita
  o django-ninja auto-gerar `components.schemas` a partir de um model
  pydantic, que colidiria com o schema injetado à mão em `export_openapi.py`
  e quebraria o freeze). Mantive o padrão: parse manual de
  `json.loads(request.body)`, validação manual, resposta como `dict` puro
  (ou tupla `(status_code, dict)`), `openapi_extra` intocado (é o que o
  freeze compara).
- Mock do provider nos testes: `unittest.mock`/`monkeypatch` direto no método
  do `MercadoPagoClient` (não `respx`) — mais simples, sem dependência nova,
  e é o ponto exato que INV-P4 pede pra contar ("1 chamada ao provider").
  `respx` ficou instalado no venv local por precaução mas NÃO entrou em
  `requirements.txt` nem é usado — evitar dependência não usada no diff.
- `MP_ACCESS_TOKEN` fica em `config/settings.py` via `env()` (fail-hard,
  mesmo padrão dos outros settings) — não adicionei nenhum runtime-check de
  prefixo `TEST-` (ex.: `assert token.startswith("TEST-")`): o INV-P8 já tem
  guarda mecanizado em `ci/guarda-de-segredos.sh` (grep por `APP_USR-` no
  repo, dona: plataforma/CI) e este despacho não lista INV-P8 como invariante
  TOCADO (só cita o CONTEXTO dele) — adicionar um guarda novo não pedido
  seria escopo fora do brief.
- Base URL da API do Mercado Pago é uma CONSTANTE no client (não env var): é
  a mesma URL para `TEST-` e para produção — quem muda o comportamento é só
  o prefixo do token, não o host.

## CI real (GitHub Actions) pegou algo que o `make ci` local não pegava

`.github/workflows/ci-celula.yml` tem um bloco `env:` fixo com as variáveis
que TODA célula precisa em CI (`DATABASE_URL`, `DJANGO_SECRET_KEY`, etc.).
Ao adicionar `MP_ACCESS_TOKEN = env("MP_ACCESS_TOKEN")` (fail-hard) em
`config/settings.py`, o CI real quebrou no target `type` (mypy importa
`config.settings` via o plugin django-stubs) com
`ImproperlyConfigured: variável obrigatória ausente: MP_ACCESS_TOKEN` — mas
localmente eu NUNCA vi isso, porque meu `.env.dev` (gitignored) já tinha
essa chave desde o início da sessão. **Lição:** toda vez que uma sessão
adicionar uma variável de ambiente obrigatória nova em `config/settings.py`
(padrão fail-hard, `CONV v1`), checar/atualizar também o bloco `env:` do
job `rodar` em `.github/workflows/ci-celula.yml` — é o único lugar que
fornece env vars pro `make -C services/$CELULA ci` real. `.env.dev` local
mascara esse tipo de esquecimento porque ele SOBREVIVE entre sessões (é
gitignored, não é recriado do zero). Corrigido com valor fake `TEST-...`
(INV-P8) na mesma linha dos outros valores fake de CI já existentes.
Consequência de orçamento: esse arquivo fica FORA de `services/pagamentos/`
mas ainda conta no `git diff --name-only origin/main...HEAD` do
`ci/orcamento-de-mudanca.sh` — precisei tirar um arquivo de teste do total
(fundido `test_intents_golden_path.py` dentro de `test_smoke.py`) pra
voltar a 15/15. Ver PR #16, segundo commit.

## Armadilhas específicas do contrato desta célula (para quem tocar `api/intents.py` de novo)

- **django-ninja: sem `response=` no decorator, só o status 200 é aceito.**
  `_result_to_response` usa `response_models = {200: NOT_SET}` quando o
  decorator não declara `response=`. Um handler que retorna `(201, dict)`
  (tupla status+corpo) estoura `ninja.errors.ConfigError: Schema for status
  201 is not set in response dict_keys([200])`. NÃO resolva isso adicionando
  `response={200: ..., 201: ...}` — qualquer valor não-`None` passado assim
  vira um `ninja.Schema` dinâmico ("NinjaResponseSchema") gerado on-the-fly,
  reintroduzindo exatamente o risco de `components.schemas` vazar pro export
  do OpenAPI e quebrar o freeze (a razão de este arquivo evitar `ninja.Schema`
  desde o esqueleto). A saída limpa: devolver um `django.http.JsonResponse(
  dict, status=201)` DIRETO — `_result_to_response` devolve `HttpResponseBase`
  sem tocar em `response_models` (checagem `isinstance(result, HttpResponseBase)`
  é a PRIMEIRA coisa que a função faz). Use isso em qualquer handler que
  precise de mais de um status de sucesso possível.
- **`.importlinter` com `type = forbidden` checa a cadeia INTEIRA por padrão**
  (import indireto conta). O contrato "metodos-so-falam-com-core" (INV-P9,
  parte 2) tinha `source_modules=[methods.pix, methods.card]`,
  `forbidden_modules=[providers]` SEM `allow_indirect_imports` — no minuto em
  que `core.gateway` de fato importou `providers.mercadopago.client` (o
  esqueleto nunca tinha chegado a esse ponto), `lint-imports` passou a
  reprovar `methods.pix -> core.gateway -> providers...` como cadeia
  proibida, mesmo essa sendo EXATAMENTE a rota que a própria
  AGENTS.pagamentos manda usar ("só através de core.gateway"). Corrigido
  adicionando `allow_indirect_imports = True` no contrato (restringe a
  checagem a import DIRETO, que é o que o contrato realmente quer dizer).
  Isso é config pré-existente no esqueleto, fora do ALVOS literal desta
  sessão (`.importlinter` fica na raiz de `services/pagamentos/`, não em
  `pagamentos/core|methods|providers|api`) — mas sem o fix, o DoD "lint-imports
  verde" é impossível com a arquitetura que a constituição pede. Se você
  tocar `core/gateway.py` ou `providers/` de novo e ver `lint-imports`
  reprovando um caminho que passa por `core.gateway`, comece por aqui antes
  de desenhar outra coisa.
- **Timezone em `DateTimeField` (USE_TZ=True):** um valor aware criado em
  memória (ex.: `datetime.fromisoformat("...-03:00")`) mantém o offset
  original ANTES de qualquer save/fetch; depois de um round-trip pelo
  Postgres, o mesmo instante volta com offset `+00:00` (o Postgres normaliza
  timestamptz para UTC). Comparar dicts com `expires_at` bruto entre "recém
  criado" e "buscado de novo via GET" quebra por formatação de string, não
  por bug — compare via `datetime.fromisoformat(...)` (mesmo instante),
  nunca string crua, quando o valor passou por um save+fetch no meio.
- **Bash tool deste ambiente não herda PATH customizado do `~/.bashrc` do
  usuário** (mesmo depois de confirmado funcionando no Git Bash interativo
  dele) — cada chamada roda uma shell nova; se precisar de um binário fora
  do PATH padrão (ex.: `make` instalado via WinGet), prefixe
  `export PATH=".../bin:$PATH" &&` no MESMO comando, não assuma que um
  `source ~/.bashrc` anterior persiste.
