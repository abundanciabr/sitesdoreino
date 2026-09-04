"""Teste-guarda de `armadilhas/029`: a sonda responde nas duas formas.

Esta célula é INTERNA: ela não tem tela, não tem endereço público, e em
produção quem a chama é o healthcheck do compose, em `/healthz`, sem prefixo
nenhum. Então por que travar o comportamento sob `SCRIPT_NAME`?

Porque a porta de máquina do degrau 7.3 (a recepção de eventos) vai nascer com
middleware, e todo middleware desta casa precisa isentar a sonda. A isenção
escrita sobre `request.path` funciona em todo teste e morre no dia em que a
célula ganhar prefixo — foi assim que a sonda do `checkout` (PR #65) e a do
`quiz` (PR #71) morreram. **O guarda é plantado ANTES de propósito**: quem
escrever a porta sobre `request.path` encontra este arquivo vermelho no
`make ci`, em vez de encontrar o container nunca ficando `healthy`.

Os dois caminhos são exercitados pelo transporte REAL de produção:

| Caminho             | Request line         | Transporte                       |
|---------------------|----------------------|----------------------------------|
| healthcheck interno | `/healthz`           | ASGI (docker compose, sem gateway) |
| borda, se existir   | `/metricas/healthz`  | ASGI (uvicorn atrás do Traefik)    |

`AsyncClient` é obrigatório para valer como prova: só ele constrói um
`ASGIRequest`, que é a classe que a célula usa em produção (`config/asgi.py`).
O `client` síncrono constrói um `WSGIRequest`, cuja aritmética de
`path`/`path_info` é diferente — mede outra coisa.
"""

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient

#: O prefixo que ESTA célula não usa hoje. Escrito à mão, e não lido de
#: `settings`: um teste que lê a mesma variável que o código passaria mesmo com
#: o valor errado.
PREFIXO_HIPOTETICO = "/metricas"


def test_healthz_pela_sonda_interna_e_o_caso_real():
    """Sem `SCRIPT_NAME`, que é como a célula roda hoje no compose."""
    resp = async_to_sync(AsyncClient().get)("/healthz")
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}
    assert resp.asgi_request.path_info == "/healthz"


@pytest.fixture
def com_prefixo(settings):
    """O dia em que esta célula ganhar borda: `SCRIPT_NAME=/metricas`."""
    settings.FORCE_SCRIPT_NAME = PREFIXO_HIPOTETICO


def test_sob_prefixo_a_sonda_responde_e_path_info_continua_curto(com_prefixo):
    """A assimetria que mata isenção escrita sobre `request.path`.

    O gateway NÃO remove o prefixo: a request line que chega ao uvicorn é
    `GET /metricas/healthz`, e nessa requisição `request.path` contém o
    prefixo em QUALQUER versão do Django. `request.path_info` segue `/healthz`
    nos dois casos, e é por ele que toda isenção desta célula tem de comparar.
    """
    resp = async_to_sync(AsyncClient().get)(f"{PREFIXO_HIPOTETICO}/healthz")
    assert resp.asgi_request.path == f"{PREFIXO_HIPOTETICO}/healthz"
    assert resp.asgi_request.path_info == "/healthz"
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"status": "ok"}


def test_sob_prefixo_a_sonda_interna_continua_respondendo(com_prefixo):
    """O healthcheck do compose chega sem prefixo, com SCRIPT_NAME ligado."""
    resp = async_to_sync(AsyncClient().get)("/healthz")
    assert resp.asgi_request.path_info == "/healthz"
    assert resp.status_code == 200, resp.content


def test_urlconf_nao_conhece_o_prefixo(client):
    """O prefixo mora no env, nunca no `urls.py`.

    Sem `SCRIPT_NAME` configurado, `/metricas/healthz` NÃO é a sonda. Se este
    teste virar 200 com o JSON de saúde, alguém embutiu `/metricas` numa rota
    e a célula deixou de ser dona do próprio endereço por configuração.

    A asserção é `!= 200` e não `== 404` de propósito: quando a porta nascer,
    esse caminho pode passar a responder outra coisa, e o que este guarda
    precisa provar continua sendo o mesmo — aquele caminho **não entrega a
    sonda**.
    """
    resposta = client.get(f"{PREFIXO_HIPOTETICO}/healthz")
    assert resposta.status_code != 200
    assert b"status" not in resposta.content
