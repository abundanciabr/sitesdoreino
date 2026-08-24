# LICOES — services/sugestoes

> Decisões e armadilhas específicas desta célula. Regra geral em `ARMADILHAS.md`
> (leia `armadilhas/INDICE.md` e abra só a entrada que casa com a sua tarefa).

## O que existe aqui hoje (Lote 1, EVO-10) — e o que NÃO existe

Esta célula nasceu como esqueleto puro: `config/` (settings fail-hard, urls,
asgi), `GET /healthz`, `apps/core` e dois arquivos de teste. **Não existe**
modelo de dados, migration, API, identidade, middleware CONV-SITE nem
`config/api.py`. Cada um tem despacho próprio (EVO-11 dados, EVO-12
sugerir/votar/comentar, EVO-13 staff). Se você chegou aqui esperando encontrar
`apps/sugestoes/models.py`, o despacho é outro — confira antes de escrever.

## O prefixo mora no env, e o `/healthz` foi travado ANTES de o middleware chegar

A Caixa serve em `meshcraft.top/forms/sugestoes/`
(`DECISAO-EVO-01-identidade.md` §2) — ou seja, **sob `SCRIPT_NAME`**, o mesmo
regime que matou a sonda do `checkout` (PR #65) e do `quiz` (PR #71). A
armadilha (`armadilhas/029`) tem duas metades, e as duas estão travadas por
`tests/test_healthz_script_name.py`:

1. `config/urls.py` **não conhece o prefixo**. Quem o aplica é
   `FORCE_SCRIPT_NAME`, lido do env. Rota escrita como
   `path("forms/sugestoes/healthz", …)` faz da mudança de URL uma cirurgia em
   código; o teste `test_urlconf_nao_conhece_o_prefixo` reprova isso.
2. Quando o middleware CONV-SITE entrar (EVO-11/EVO-12), a isenção de
   `/healthz` compara **`request.path_info`**, nunca `request.path`. Pela borda
   pública o Traefik NÃO remove o prefixo: a request line que chega ao uvicorn
   é `GET /forms/sugestoes/healthz`, e aí `request.path` contém o prefixo em
   qualquer versão do Django.

**O guarda usa `AsyncClient`, e isso não é preciosismo.** Em produção a célula
roda sob uvicorn, logo o objeto de requisição é `ASGIRequest` — que faz
`path = scope["path"]` e `path_info = path.removeprefix(script_name)`. O
`client` síncrono do Django constrói um `WSGIRequest`, cuja aritmética é a
inversa (`path_info` vem do environ como está, `path = script_name + path_info`).
Testar a borda pública pelo client síncrono mediria outra coisa. Detalhe que
custa tempo se descoberto na hora errada: no `AsyncClient` a requisição sai por
`resp.asgi_request`, **não** `resp.wsgi_request` (que só existe no síncrono, e
é o que os testes das outras células usam).

## O compose de dev foge do molde em duas linhas, de propósito

`docker-compose.dev.yml` das outras 8 células usa `name: dev-celula` e mapeia o
Postgres em `5432`. Aqui é `name: dev-sugestoes`, `container_name:
sugestoes-pg-dev` e `55440:5432`.

O nome do projeto do compose é o **namespace dos containers**: com
`dev-celula` em todas, duas sessões de agente rodando em paralelo (o modo de
trabalho normal desta casa — `RUNBOOK-LOTES.md`) disputam o mesmo
`dev-celula-db-1`, e a segunda derruba o banco da primeira sem avisar. A porta
55440 é a pré-atribuída a esta célula, para não colidir com o `55432` da
partida rápida do `ARMADILHAS.md` §2.

**Isso é dívida das outras 8, não invenção desta.** Se alguém uniformizar, o
caminho é uniformizar para o nome por célula, não de volta para `dev-celula`.

## Fail-hard: só as duas variáveis que o CI já fornece

`config/settings.py` levanta `ImproperlyConfigured` no import para
`DJANGO_SECRET_KEY` e `DATABASE_URL` — e mais nada. O motivo é mecânico
(`armadilhas/037`): variável nova e fail-hard no `settings.py` precisa ser
espelhada no bloco `env:` de `.github/workflows/ci-celula.yml`, que é o único
lugar que alimenta o `make ci` do CI real — e `.github/` está fora do escopo
desta célula. As variáveis que ainda vão nascer aqui
(`SUGESTOES_STAFF_EMAILS`, `ALUNOS_API_URL`, `TOKEN_ALUNOS`, credenciais do
Google) são lidas **no ponto de uso**, com default inofensivo, como manda a
convenção do lote de Huey. `SCRIPT_NAME` já segue essa forma
(`os.environ.get(...) or None`).

## `contrato-check` veio do template, não do vizinho

O `Makefile` desta célula usa `bash ../../ci/freeze-de-contrato.sh $(CELULA)`
— a forma do `celula-template/`. O `Makefile` de `quiz` e `funil` ainda usa a
forma antiga (`if [ -f ../../contracts/… ]` + escrita em `/tmp`), que tem dois
problemas: infere "não tem contrato" de "não achei o arquivo" (exatamente a
ambiguidade que o `ci/manifesto-de-contratos.json` foi criado para matar,
INV-CI01) e escreve em `/tmp`, que não existe na máquina Windows do
mantenedor. Quem decide é o manifesto, e nele esta célula é
`freeze: not-applicable`.

## Por que `not-applicable` aqui não envelhece como o de `funil`/`quiz`

O `reason` de `funil`, `mensageria` e `quiz` diz "célula ainda em esqueleto: só
`/healthz`" — um motivo que caduca no dia em que a célula ganhar API. O desta
não caduca, porque não é sobre maturidade: `contracts/` é a fronteira **ENTRE**
células (`contracts/README.md`), e a superfície HTTP da Caixa é consumida pelo
front-end **dela mesma**. Mesmo depois de EVO-12, com sugerir/votar/comentar no
ar, continua não havendo contrato a congelar. Só muda se outra célula precisar
consumir a Caixa — e aí é RITOS.md §3, não edição de manifesto.
