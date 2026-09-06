"""Teste-guarda de `armadilhas/029`: `/healthz` sob prefixo.

Esta célula serve em `meshcraft.top/pages` (`PLANO-PORTFOLIO-DO-ALUNO.md` §4),
ou seja **sob SCRIPT_NAME** — a mesma condição que derrubou a sonda do
`checkout` (PR #65) e do `quiz` (PR #71), e que a `sugestoes`, a `admin`, o
`forum`, a `gamificacao`, a `encomendas` e a `cursos` já travam do mesmo jeito.
Duas coisas quebram nesse regime, e as duas estão travadas aqui:

1. **O urlconf não pode conhecer o prefixo.** Quem o aplica é
   `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Uma rota escrita
   como `path("pages/healthz", ...)` deixa de resolver assim que o prefixo
   muda — e mudar de endereço passaria a exigir cirurgia em código. Nesta
   célula isso é mais do que higiene: ela tem DOIS endereços públicos
   (`/pages` e `/estudio`), e a decisão de qual deles vira `SCRIPT_NAME` é do
   degrau 05. Um urlconf que já tivesse cravado um deles tomaria essa decisão
   sozinho, aqui, sem poder prová-la.
2. **Qualquer isenção de middleware compara `request.path_info`, nunca
   `request.path`.** Pela borda pública o Traefik **não remove** o prefixo: a
   request line que chega ao uvicorn é `GET /pages/healthz`, e nessa
   requisição `request.path` contém o prefixo em QUALQUER versão do Django.
   `request.path_info` segue `/healthz` nos dois casos.

Esta célula ainda não tem middleware próprio — a porta nasce no degrau 06. **O
guarda é plantado ANTES de propósito**: quem escrever a porta sobre
`request.path` encontra este arquivo vermelho no `make ci`, em vez de encontrar
a sonda morta em produção e o container nunca ficando `healthy`.

E há um terceiro efeito do mesmo corte, que este arquivo mede de passagem e que
`armadilhas/186` documenta: como o Django é quem remove o prefixo, tudo o que
esta célula servir na raiz do urlconf fica alcançável em `/pages/<caminho>`
pela internet. Vale para o `/healthz` (o que é desejado) e valerá para
`/api/pages/` e `/interno/` da porta de máquina do degrau 03 (o que exige
Bearer, não topologia). O `test_o_prefixo_alcanca_a_raiz_do_urlconf` abaixo é a
prova dessa premissa, escrita agora para que ninguém copie de uma célula
vizinha a frase *"nada em `/interno` resolve pela borda pública"* — que aqui
seria FALSA.

Os dois caminhos de entrada são exercitados pelo transporte REAL de cada um:

| Caminho             | Request line      | Transporte                         |
|---------------------|-------------------|------------------------------------|
| borda pública       | `/pages/healthz`  | ASGI (uvicorn atrás do Traefik)    |
| healthcheck interno | `/healthz`        | ASGI (docker compose, sem gateway) |

`AsyncClient` é obrigatório para valer como prova: só ele constrói um
`ASGIRequest`, que é a classe que a célula usa em produção (`config/asgi.py`).
O `client` síncrono constrói um `WSGIRequest`, cuja aritmética de
`path`/`path_info` é diferente — mede outra coisa.
"""

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient

# O prefixo público real da célula, que o env da VPS vai carregar (degrau 04,
# `infra/provisionar-pages.sh` e o env de exemplo). Escrito à mão aqui, e não
# lido de `settings`: um teste que lê a mesma variável que o código passaria
# mesmo com o valor errado.
PREFIXO = "/pages"


@pytest.fixture
def env_de_producao(settings):
    """O que o env real da VPS faz: SCRIPT_NAME=/pages."""
    settings.FORCE_SCRIPT_NAME = PREFIXO


def test_healthz_pela_borda_publica_com_prefixo(env_de_producao):
    """O cenário que já morreu em produção: o gateway NÃO remove o prefixo."""
    resp = async_to_sync(AsyncClient().get)(f"{PREFIXO}/healthz")
    # Sanidade do cenário: é ESTA a assimetria que derruba a isenção escrita
    # sobre `request.path`.
    assert resp.asgi_request.path == f"{PREFIXO}/healthz"
    assert resp.asgi_request.path_info == "/healthz"
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}


def test_healthz_pela_sonda_interna_com_prefixo_configurado(env_de_producao):
    """O healthcheck do compose: chega sem prefixo, com SCRIPT_NAME ligado."""
    resp = async_to_sync(AsyncClient().get)("/healthz")
    assert resp.asgi_request.path_info == "/healthz"
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}


def test_o_prefixo_alcanca_a_raiz_do_urlconf(env_de_producao):
    """`armadilhas/186`: quem corta o prefixo é o Django, não o Traefik.

    A consequência que este guarda fixa em teste, para que ela pare de ser
    crença: com `FORCE_SCRIPT_NAME` ligado, uma rota declarada na RAIZ do
    urlconf é servida em `/pages/<rota>` pela internet. É por isso que o
    `/healthz` funciona pela borda — e é exatamente por isso que a porta de
    máquina do degrau 03 (`/api/pages/`, `/interno/`) NÃO poderá contar com a
    topologia para ficar escondida: ela nascerá publicada, e quem a fecha é o
    Bearer do par.

    A medida é o `path_info` já cortado: se um dia o corte deixar de acontecer,
    esta asserção cai e o comentário do `config/urls.py` deixa de estar sozinho
    defendendo a afirmação.
    """
    resp = async_to_sync(AsyncClient().get)(f"{PREFIXO}/healthz")
    assert resp.asgi_request.path_info == "/healthz", (
        "o prefixo não foi removido do path_info — a premissa de "
        "armadilhas/186 mudou, e o comentário do config/urls.py precisa "
        "ser reescrito"
    )
    assert resp.status_code == 200


def test_urlconf_nao_conhece_o_prefixo(client):
    """O outro lado da moeda: o prefixo mora no env, nunca no `urls.py`.

    Sem SCRIPT_NAME configurado, `/pages/healthz` NÃO é a sonda — se este teste
    virar 200 com o JSON de saúde, alguém embutiu `/pages` numa rota e a célula
    deixou de ser dona do próprio prefixo por configuração.

    A asserção não é `== 404` de propósito: a gênese já sabia que a forma da
    resposta mudaria quando a porta nascesse (degrau 06), e o que este guarda
    precisa provar continua sendo o mesmo — aquele caminho **não entrega a
    sonda**.

    **A porta nasceu em 05/09/2026, e a previsão da gênese errou a forma.** Ela
    escreveu `status_code != 200`, esperando um redirecionamento para o login.
    A porta que nasceu não redireciona: ela devolve a página que explica o que
    aconteceu e o que fazer, com HTTP 200 para quem é visitante (critério
    AC-05, `apps/core/porta.py`). O caminho continua não entregando a sonda, e
    é isso que as duas asserções abaixo medem agora, sem depender de qual
    número a recusa carrega.
    """
    resposta = client.get(f"{PREFIXO}/healthz")
    assert "application/json" not in resposta["Content-Type"]
    assert b"status" not in resposta.content
