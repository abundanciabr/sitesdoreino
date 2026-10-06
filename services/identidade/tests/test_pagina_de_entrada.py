from urllib.parse import parse_qs, urlsplit

import pytest


@pytest.mark.parametrize("parametro", ["next", "proxima"])
def test_link_de_entrada_preserva_volta_ao_sandbox(client, parametro):
    caminho = "/encomendas/sandbox/?categoria=pets&projeto=mascote-3d"
    resposta = client.get("/entrar", {parametro: caminho})
    assert resposta.status_code == 302
    destino = urlsplit(resposta["Location"])
    assert destino.path == "/login"
    assert parse_qs(destino.query)["next"] == [caminho]
    assert not resposta.cookies


@pytest.mark.parametrize("destino", ["https://outro.example/", "//outro.example/", "/\\outro.example/", "/x\ny"])
def test_link_de_entrada_recusa_destino_externo(client, destino):
    resposta = client.get("/entrar", {"proxima": destino})
    assert resposta["Location"] == "/login?next=%2F"


def test_entrada_sem_destino_e_com_next_prioritario(client):
    assert client.get("/entrar")["Location"] == "/login?next=%2F"
    resposta = client.get("/entrar", {"next": "/es/curso", "proxima": "/encomendas/sandbox/"})
    assert resposta["Location"] == "/es/login?next=%2Fes%2Fcurso"
