"""Teste-guarda de armadilhas/029 (ex-ARMADILHAS §4.10): /healthz sob prefixo.

A Caixa de Sugestões serve em `meshcraft.top/forms/sugestoes/`
(`DECISAO-EVO-01-identidade.md` §2), ou seja **sob SCRIPT_NAME** — a mesma
condição que derrubou a sonda do `checkout` (PR #65) e do `quiz` (PR #71). Duas
coisas quebram nesse regime, e as duas estão travadas aqui:

1. **O urlconf não pode conhecer o prefixo.** Quem o aplica é
   `FORCE_SCRIPT_NAME`, lido do env em `config/settings.py`. Uma rota escrita
   como `path("forms/sugestoes/healthz", ...)` deixa de resolver assim que o
   prefixo muda — e mudar de URL passa a exigir cirurgia em código.
2. **Qualquer isenção de middleware compara `request.path_info`, nunca
   `request.path`.** Pela borda pública o Traefik **não remove** o prefixo: a
   request line que chega ao uvicorn é `GET /forms/sugestoes/healthz`, e nessa
   requisição `request.path` contém o prefixo em QUALQUER versão do Django
   (medido ao vivo em 22/08/2026: `https://basileiatoutheou.org/quiz/healthz`
   respondia 404 enquanto a sonda interna `localhost:8000/healthz` respondia
   200). `request.path_info` segue `/healthz` nos dois casos.

Esta célula ainda não tem middleware CONV-SITE (nasce sem regra de negócio —
EVO-11/EVO-12 o trazem). O guarda é plantado ANTES de propósito: quem
instalar o middleware e escrever a isenção sobre `request.path` encontra este
arquivo vermelho no `make ci`, em vez de encontrar a sonda morta em produção.

Os dois caminhos de entrada são exercitados pelo transporte REAL de cada um:

| Caminho             | Request line                | Transporte |
|---------------------|-----------------------------|------------|
| borda pública       | `/forms/sugestoes/healthz`  | ASGI (uvicorn atrás do Traefik) |
| healthcheck interno | `/healthz`                  | ASGI (docker compose, sem gateway) |

`AsyncClient` é obrigatório para valer como prova: só ele constrói um
`ASGIRequest`, que é a classe que a célula usa em produção (`config/asgi.py`).
O `client` síncrono constrói um `WSGIRequest`, cuja aritmética de
`path`/`path_info` é diferente — mede outra coisa.
"""

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient

# O prefixo público real da célula (infra/env, Lote 2). Escrito à mão aqui, e
# não lido de settings: um teste que lê a mesma variável que o código passaria
# mesmo com o valor errado.
PREFIXO = "/forms/sugestoes"


@pytest.fixture
def env_de_producao(settings):
    """O que o env real da VPS faz: SCRIPT_NAME=/forms/sugestoes."""
    settings.FORCE_SCRIPT_NAME = PREFIXO


def test_healthz_pela_borda_publica_com_prefixo(env_de_producao):
    """O cenário que morreu em produção: o gateway NÃO remove o prefixo."""
    resp = async_to_sync(AsyncClient().get)(f"{PREFIXO}/healthz")
    # Sanidade do cenário: é ESTA a assimetria que derruba a isenção escrita
    # sobre request.path.
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


def test_urlconf_nao_conhece_o_prefixo(client):
    """O outro lado da moeda: o prefixo mora no env, nunca no urls.py.

    Sem SCRIPT_NAME configurado, o caminho prefixado NÃO existe — se este
    teste virar 200, alguém embutiu `/forms/sugestoes` numa rota e a célula
    deixou de ser dona do próprio prefixo por configuração.
    """
    assert client.get(f"{PREFIXO}/healthz").status_code == 404
