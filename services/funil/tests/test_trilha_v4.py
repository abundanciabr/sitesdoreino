"""A entrada pública nunca entrega a trilha ou seus dados."""

import pytest
from conftest import HOST_A, HOST_MESH


def test_entrada_leva_para_porta_do_admin(client, rede):
    resposta = client.get("/trilha/", {"aluno": "matricula-123"}, HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 302
    assert resposta["Location"] == "/admin/trilha/?aluno=matricula-123"
    assert "no-store" in resposta["Cache-Control"]
    assert "noindex" in resposta["X-Robots-Tag"]
    assert b"trilha-data" not in resposta.content


@pytest.mark.parametrize("caminho", [
    "/trilha/style.css", "/trilha/app.js",
    "/static/funil/trilha-v4/index.html",
    "/static/funil/trilha-v4/style.css",
    "/static/funil/trilha-v4/app.js",
])
def test_arquivos_nao_existem_na_area_publica(client, rede, caminho):
    assert client.get(caminho, HTTP_HOST=HOST_MESH).status_code == 404


def test_barra_no_endereco(client, rede):
    resposta = client.get("/trilha", HTTP_HOST=HOST_MESH)
    assert resposta.status_code == 301
    assert resposta["Location"] == "/trilha/"


def test_trilha_apenas_no_meshcraft(client, rede):
    assert client.get("/trilha/", HTTP_HOST=HOST_A).status_code == 404


def test_nao_recebe_projetos_ou_altera_progresso(client, rede):
    assert client.post("/trilha/", HTTP_HOST=HOST_MESH).status_code == 405
