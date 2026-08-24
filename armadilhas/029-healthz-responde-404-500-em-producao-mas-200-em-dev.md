<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.10  ·  referencias antigas "ARMADILHAS §4.10" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.10 `/healthz` responde 404/500 em produção, mas 200 em dev — `SCRIPT_NAME` + Django 5.0

**Sintoma:** a mesma imagem que devolve `200 {"status": "ok"}` em `GET /healthz`
localmente devolve **404** (ou 500, se a resolução de site fizer uma chamada HTTP que
falha) quando sobe com o `env/*.env` de produção. Efeito prático: healthcheck de
container nunca fica `healthy`, e qualquer serviço com
`depends_on: condition: service_healthy` **nunca sobe**.
**Causa:** a isenção do middleware CONV-SITE (§4.5) é escrita como
`request.path.startswith(("/healthz", "/static/"))`, e `request.path` **inclui o
script name**. Com `SCRIPT_NAME=/checkout` no env de produção, `FORCE_SCRIPT_NAME`
faz `request.path` virar `/checkout/healthz` — a isenção não casa, o middleware tenta
resolver o site a partir do Host `localhost`, não acha, e levanta `Http404`.
`request.path_info` continua `/healthz` (por isso a URL **resolve** normalmente; quem
erra é só a comparação).

E depende da versão do Django — as duas convivem neste repositório:

| Django | `ASGIRequest.__init__` | `request.path` com `FORCE_SCRIPT_NAME=/checkout` |
|---|---|---|
| **5.0.9** (alunos, catalogo, checkout, leads, pagamentos) | `self.path = script_name.rstrip("/") + "/" + path_info[1:]` | `/checkout/healthz` ⇒ **quebra** |
| **5.1.4** (funil, mensageria, quiz) | `self.path = scope["path"]` | `/healthz` ⇒ funciona |

Ou seja: a armadilha só dispara onde as **três** coisas coincidem — `SCRIPT_NAME` no
env, middleware CONV-SITE na célula, e Django 5.0.x. Hoje isso é **só `checkout`**
(medido nas 8 células em 21/08/2026 com `infra/env/*.exemplo`: 7 respondem 200,
`checkout` responde 404). `quiz` tem `SCRIPT_NAME` e middleware, mas está em 5.1.4;
`alunos` tem `SCRIPT_NAME` e 5.0.9, mas não tem middleware. Qualquer uma das três
muda ⇒ mais uma célula cai, **em silêncio**.

**Solução:** no middleware, comparar `request.path_info`, não `request.path` — é o
caminho independente de prefixo de gateway. Enquanto a célula não for corrigida
(ARMADILHAS §1/H10), o contorno em `infra/docker-compose.yml` é sondar o socket TCP
em vez do HTTP: prova que o `migrate` do `CMD` terminou e o uvicorn subiu, que é tudo
o que o `depends_on` precisa saber.

**Como medir sem adivinhar** (roda contra a imagem, com o env real da célula):

```bash
docker run -d --name sonda --env-file infra/env/<celula>.env <imagem>
docker exec sonda python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/healthz').status)"
```

⚠ **No Git Bash, passe o env por `--env-file`, nunca por `-e SCRIPT_NAME=/checkout`:**
o MSYS converte o `/checkout` em `C:/Program Files/Git/checkout` (§3.7) e o teste
mede outra coisa — foi exatamente isso que fez a primeira rodada desta medição dar
um resultado sem sentido (`quiz` "passando" por motivo errado).

**De quebra:** `ALLOWED_HOSTS` nos `infra/env/*.exemplo` é decorativo — as 8 células
têm `ALLOWED_HOSTS = ["*"]` fixo no `config/settings.py` e **não leem** essa variável.
Por isso a sonda com `Host: localhost` passa mesmo em `catalogo`/`leads`/`mensageria`,
cujo exemplo diz `ALLOWED_HOSTS=<nome-da-célula>`.
**Origem:** despacho infra/consumers — ao acrescentar healthcheck ao bloco `x-celula`.
**Atualização (lote 2, 22/08/2026) — Django 5.1 NÃO imuniza quando o acesso vem
pelo gateway:** a tabela acima mede a sonda INTERNA (request line `/healthz`, sem
prefixo). Pela borda pública o Traefik NÃO remove o prefixo — a request line é
`/quiz/healthz` — e aí `request.path` contém o prefixo em QUALQUER versão do
Django. Medido: `quiz` (5.1.4) respondia 404 em `/quiz/healthz` pela internet até
o PR #71 trocar a comparação para `request.path_info`. A regra vale para toda
célula com middleware: a isenção compara `path_info`, sempre.
