"""Guarda de armadilhas/029, terceira temporada: a VOLTA sob `SCRIPT_NAME`.

O OAuth saiu desta célula (DECISAO-celula-de-identidade) e levou embora o
`redirect_uri` — mas o problema de prefixo NÃO foi embora: o botão de entrar
manda a pessoa à porta central com `?next=<a porta desta Caixa>`, e esse
`next` precisa carregar o prefixo público (`/forms/sugestoes/entrar`). Um
`next` sem prefixo devolveria quem entrou para um `/entrar` que NÃO EXISTE —
em produção, e só lá, porque em dev não há prefixo para faltar.

Quem carrega o prefixo é `reverse()` + `FORCE_SCRIPT_NAME`, nunca string à mão
(`apps/core/views.py::_para_a_porta_central`). `AsyncClient` pelo mesmo motivo
do guarda do `/healthz`: só ele constrói o `ASGIRequest` de produção.
"""

from urllib.parse import parse_qs, urlparse

import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient
from django.urls import clear_script_prefix, set_script_prefix

PREFIXO = "/forms/sugestoes"


@pytest.fixture
def sob_prefixo(settings):
    """O env da VPS — MAIS o que o servidor de verdade faz e o client não faz.

    `reverse()` não lê `settings.FORCE_SCRIPT_NAME`: lê um prefixo de thread
    que o `ASGIHandler` real preenche na porta de entrada e o client de teste
    não preenche (a lição inteira está no guarda-irmão
    `test_healthz_script_name.py`). Emular o servidor aqui é cenário, não
    código sob teste; e o prefixo de thread não é limpo entre testes — daí o
    `clear_script_prefix()` na saída.
    """
    settings.FORCE_SCRIPT_NAME = PREFIXO
    set_script_prefix(PREFIXO)
    yield
    clear_script_prefix()


def _bater(caminho: str):
    """Uma requisição como o Traefik entrega: prefixo inteiro na request line."""
    return async_to_sync(AsyncClient().get)(PREFIXO + caminho)


def test_o_next_do_botao_carrega_o_prefixo_publico(sob_prefixo, db):
    resposta = _bater("/entrar/google")

    assert resposta.status_code == 302, resposta.content
    destino = urlparse(resposta["Location"])
    assert destino.path == "/entrar/google", "a porta central é SEM prefixo"
    proximo = parse_qs(destino.query)["next"][0]
    assert proximo == f"{PREFIXO}/entrar", (
        "o next sem o prefixo devolveria quem entrou para um /entrar que não "
        "existe — armadilhas/029, em produção e só lá"
    )


def test_o_retorno_legado_aterrissa_na_porta_com_prefixo(sob_prefixo, db):
    resposta = _bater("/entrar/google/retorno")

    assert resposta.status_code == 302
    assert resposta["Location"] == f"{PREFIXO}/entrar"
