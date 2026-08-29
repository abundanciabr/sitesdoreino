# `conn_max_age` > 0 sob ASGI vaza UMA conexão de banco por requisição — e o teste não vê nada

**Sintoma:** o Postgres da plataforma bate no teto de conexões
(`FATAL: sorry, too many clients already`, ou requisições que voltam como erro
sob rajada) numa página que nem é pesada. A célula está saudável, o `/healthz`
responde 200, a suíte é verde, o deploy fechou `success`. `pg_stat_activity`
mostra dezenas de conexões `idle` de um serviço que tem **um** processo e
poucos usuários.

**Causa:** `conn_max_age` maior que zero num serviço servido por **ASGI**
(uvicorn, daphne). São três fatos verdadeiros que só juntos viram vazamento:

1. `ASGIHandler.__call__` abre `async with ThreadSensitiveContext()` **por
   requisição** (`django/core/handlers/asgi.py`), e o asgiref cria um
   `ThreadPoolExecutor(max_workers=1)` para cada contexto — **uma thread nova
   por requisição**, sem teto.
2. A conexão de banco do Django é **thread-local** (`django/db/utils.py`,
   `thread_critical=True`).
3. No fim da requisição o Django chama `await sync_to_async(response.close)()`,
   que dispara `request_finished` → `close_old_connections` →
   `close_if_unusable_or_obsolete()`. Esse método só fecha a conexão se ela
   estiver **obsoleta** — `time.monotonic() >= self.close_at`.

Com `conn_max_age=0` (o default do Django e do `dj_database_url`), `close_at`
já venceu no instante em que a conexão nasceu: ela fecha, e **não há
vazamento**. Com `conn_max_age=60`, `close_at` está 60s no futuro: a conexão
**não** fecha, a thread dona dela é descartada logo em seguida, e não sobra
ninguém com uma referência para fechá-la.

**Por que escapa de tudo o que existe:** a suíte roda em WSGI (o `Client` de
teste do Django), onde uma thread atende várias requisições — o cenário do bug
nem existe. O `/healthz` continua 200 porque conexão sobrando não derruba
processo nenhum. E o ajuste costuma ter sido posto por uma medição **correta**:
no caso real, conexão nova + `SELECT` custava ~24 ms contra ~0,2 ms
reaproveitando — o ganho é verdadeiro, o efeito colateral é que não foi medido.

**A pista que aponta a célula certa, em um comando:**

```bash
git grep -n "conn_max_age\|CONN_MAX_AGE" -- services/
```

Zero ocorrências numa célula = ela usa o default `0` e **não** é esta armadilha.
No caso medido (28/08/2026) havia **uma** ocorrência entre 13 células — e era
exatamente a que estourava, porque toda página logada do site passa por ela.

**Solução — e não é voltar para `conn_max_age=0`:** isso fecharia o vazamento
devolvendo os ~24 ms a toda requisição. Use o **pool nativo do Django 5.1**:

```python
DATABASES = {"default": dj_database_url.parse(env("DATABASE_URL"))}  # CONN_MAX_AGE = 0
DATABASES["default"]["OPTIONS"] = {
    **DATABASES["default"].get("OPTIONS", {}),
    "pool": {"min_size": 1, "max_size": 8, "timeout": 10},
}
```

e `psycopg[binary,pool]` no `requirements.txt` (o extra `pool` traz o
`psycopg_pool`; sem ele a célula **sobe** e só quebra na primeira consulta).

O que faz o pool ser a resposta certa, e não outro paliativo:
`_connection_pools` é atributo de **CLASSE** do `DatabaseWrapper`
(`django/db/backends/postgresql/base.py`) — o pool é do **processo**, não da
thread. Thread descartada **devolve** a conexão. E `max_size` põe um teto que
antes não existia: a célula deixa de poder consumir o banco inteiro sozinha.

Duas exigências do Django que mordem se você esquecer:

- `CONN_MAX_AGE` tem de ser **0**, senão `ImproperlyConfigured: Pooling doesn't
  support persistent connections` — é por isso que o argumento **some** do
  `parse()`, e não por descuido de quem editou.
- sem `psycopg_pool` instalado: `ImproperlyConfigured: Error loading
  psycopg_pool module. Did you install psycopg[pool]?`

**O guarda, que não precisa de banco:** o pool nasce com `open=False`, então
`connections["default"].pool` pode ser inspecionado numa suíte sem Postgres. Um
único `assert` cobre as **três** regressões (pool removido ⇒ `None`;
`conn_max_age` de volta ⇒ `ImproperlyConfigured`; extra fora do requirements ⇒
`ImproperlyConfigured`). Acrescente o teste que prova que o pool é do
**processo** — quatro threads pegando `connections["default"].pool` têm de
receber o MESMO objeto — e, dentro dele, um `assert pool is not None`: sem esse
assert o teste fica verde com o pool desligado, porque `None` é o mesmo objeto
em toda thread (`armadilhas/129`, guarda que não mede).

**Origem:** sessão de esvaziamento da caixa "Precisa de você", 28/08/2026,
célula `identidade` (PR #422). O registro `20260827-036` do livro tinha
diagnosticado o mecanismo corretamente **e generalizado para as 13 células** —
a leitura do código instalado mostrou que doze estavam certas o tempo todo. É a
diferença entre ler o comportamento padrão e ler a configuração desta célula
(`RETROSPECTIVA-FASE-D` §8). **Categoria**: falso-verde (a suíte WSGI não
encena o cenário) · viabilidade sem ler a config.
