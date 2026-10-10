"""A V4 pública preserva a página aprovada e resolve seus recursos relativos."""

import pytest

from apps.core.trilha_v4 import ARQUIVOS
from conftest import HOST_A, HOST_MESH


@pytest.mark.parametrize(
    "caminho,arquivo,tipo",
    [
        ("/trilha/", "index.html", "text/html"),
        ("/trilha/style.css", "style.css", "text/css"),
        ("/trilha/app.js", "app.js", "text/javascript"),
    ],
)
def test_pagina_e_recursos(client, rede, caminho, arquivo, tipo):
    resposta = client.get(caminho, HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 200
    assert resposta["Content-Type"].startswith(tipo)
    assert resposta.content == (ARQUIVOS / arquivo).read_bytes()
    cabecalho = client.head(caminho, HTTP_HOST=HOST_MESH)
    assert cabecalho.status_code == 200
    assert cabecalho.content == b""


def test_barra_preserva_base_dos_recursos_relativos(client, rede):
    resposta = client.get("/trilha", HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 301
    assert resposta["Location"] == "/trilha/"


def test_trilha_apenas_no_meshcraft(client, rede):
    assert client.get("/trilha/", HTTP_HOST=HOST_A).status_code == 404


def test_nao_recebe_projetos_ou_altera_progresso(client, rede):
    assert client.post("/trilha/", HTTP_HOST=HOST_MESH).status_code == 405
