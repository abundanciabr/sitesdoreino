# `Failed: Redis real inacessível em redis://localhost:6379/0` — a partida rápida sobe o Postgres e esquece o Redis, e o baseline nasce vermelho sem culpa sua

**Sintoma:** você seguiu a partida rápida (`ARMADILHAS.md` §2) à risca — worktree,
container do Postgres, as três variáveis — e o baseline VERDE que o `RITOS.md` §1
exige antes de tocar em qualquer arquivo não vem:

```
$ make ci
...
>           pytest.fail(
E           Failed: Redis real inacessível em redis://localhost:6379/0 — suba o container antes de rodar.
=========================== short test summary info ===========================
ERROR tests/test_reentrega_pel.py::test_mensagem_presa_e_reivindicada_e_o_efeito_acontece
ERROR tests/test_reentrega_pel.py::test_mensagem_recem_entregue_nao_e_reivindicada
ERROR tests/test_reentrega_pel.py::test_na_quinta_entrega_vai_para_fila_morta_e_handler_nao_roda
16 passed, 4 warnings, 3 errors in 18.67s
make: *** [Makefile:14: test] Error 1
```

O risco não é o vermelho — é a leitura dele. "O baseline não está verde, então a
main está quebrada, então paro e reporto" é a regra certa do rito, e aqui ela leva
à conclusão errada: **isto é instrumento faltando na sua máquina, não main
quebrada**. Um despacho inteiro pode ser abortado por causa disso.

**Causa:** a partida rápida do §2 sobe **um** container (Postgres) e exporta
**três** variáveis (`PYTHONUTF8`, `DJANGO_SECRET_KEY`, `DATABASE_URL`). O
`.github/workflows/ci-celula.yml` declara **dois** serviços (Postgres **e Redis**)
e **sete** variáveis — as três do §2 mais `REDIS_STREAMS_URL`, `HUEY_REDIS_URL` e,
só em `pagamentos`, `MP_ACCESS_TOKEN` e `MP_WEBHOOK_SECRET`. As células que
consomem o fio de eventos (PEL / Redis Streams) têm testes que **exigem um Redis
de verdade e se recusam a rodar com dublê** — deliberadamente, porque reentrega e
fila morta são o tipo de coisa que um mock aprova sem provar nada.

Ou seja: o §2 é uma partida rápida de célula **sem fio de eventos**, e nada no
texto avisa que ele encolhe conforme a célula.

**Solução — dois comandos, uma vez por máquina:**

```bash
# 1. Os DOIS containers (o Redis serve todas as células ao mesmo tempo)
docker run -d --name <celula>-pg -e POSTGRES_USER=dev -e POSTGRES_PASSWORD=dev \
  -e POSTGRES_DB=<celula>_db -p 55432:5432 postgres:17
docker run -d --name ci-redis -p 6379:6379 redis:7

# 2. O ambiente COMPLETO da sessão (as 3 do §2 + as do fio de eventos)
export PYTHONUTF8=1
export DJANGO_SECRET_KEY="ci-apenas-nunca-em-producao"
export DATABASE_URL="postgres://dev:dev@localhost:55432/<celula>_db"
export REDIS_STREAMS_URL="redis://localhost:6379/0"
export HUEY_REDIS_URL="redis://localhost:6379/1"
# só em pagamentos (INV-P8 / INV-P10 — fail-hard deliberado no settings.py):
export MP_ACCESS_TOKEN="TEST-ci-0000000000000000-000000-fake000000000000000000000000000-000000000"
export MP_WEBHOOK_SECRET="ci-apenas-nunca-em-producao-webhook-secret"
```

Um Redis só atende todas as células — cada uma usa um banco numerado diferente
dentro dele, e o mesmo container serve worktrees paralelos. O Postgres também: o
`pytest-django` cria `test_<celula>_db` dentro da mesma instância, então o
container de qualquer célula serve as outras trocando só o nome no `DATABASE_URL`.

**A regra que generaliza, e é a parte que vale relembrar:** quando o baseline
local não fecha, a primeira pergunta é *"o que a CI tem que eu não tenho?"* — e a
resposta está escrita, sempre no mesmo lugar: o bloco `env:` e o bloco `services:`
do `.github/workflows/ci-celula.yml`. Ele é a definição executável do ambiente; o
§2 é um resumo, e resumo envelhece. Confira o workflow **antes** de concluir que a
main está quebrada. Vermelho por instrumento ausente é ERROR, não FAIL — e a
diferença entre os dois decide se o despacho continua ou para.

**Origem:** despacho `H12 — contrato-check pelo manifesto` (lote de 25/08/2026), ao
levantar o baseline de oito células seguidas. O erro do Redis apareceu na primeira
(`alunos`) e a leitura literal do rito mandaria abortar as oito.
