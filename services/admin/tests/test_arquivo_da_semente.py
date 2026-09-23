"""Arquivos versionados ao lado do documento aparecem sem envio manual."""

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento, Midia

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 60


@pytest.fixture
def pasta_semente(tmp_path, monkeypatch):
    pasta = tmp_path / "documentos"
    pasta.mkdir()
    monkeypatch.setattr(documentos, "diretorio", lambda: pasta)
    return pasta


def colocar(pasta, arquivo, conteudo):
    destino = pasta / "um-guia"
    destino.mkdir(exist_ok=True)
    (destino / arquivo).write_bytes(conteudo)


def test_imagem_e_video_da_semente_aparecem_no_documento(pasta_semente, db):
    colocar(pasta_semente, "foto.png", PNG)
    colocar(pasta_semente, "clipe.mp4", MP4)
    documento = Documento.objects.create(
        nome="um-guia",
        titulo="Um guia",
        corpo="![Foto](arquivo:foto)\n\n![Clipe](arquivo:clipe)",
        publico=True,
    )

    corpo = documentos.para_html(documento.corpo, documento=documento)

    assert '<img src="/docs/um-guia/arquivo/foto.png"' in corpo
    assert '<video controls src="/docs/um-guia/arquivo/clipe.mp4">' in corpo
    resposta = Client().get("/docs/um-guia/arquivo/foto.png")
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/png"
    assert b"".join(resposta.streaming_content) == PNG


def test_arquivo_privado_nao_aparece_sem_acesso(pasta_semente, db):
    colocar(pasta_semente, "foto.png", PNG)
    Documento.objects.create(nome="um-guia", titulo="Um guia", corpo="", publico=False)

    assert Client().get("/docs/um-guia/arquivo/foto.png").status_code == 404


def test_arquivo_invalido_nao_gera_imagem(pasta_semente, db):
    colocar(pasta_semente, "foto.png", b"<html><script>alert(1)</script></html>")
    documento = Documento.objects.create(
        nome="um-guia", titulo="Um guia", corpo="![Foto](arquivo:foto)"
    )

    corpo = documentos.para_html(documento.corpo, documento=documento)

    assert "<img" not in corpo
    assert "arquivo:foto" in corpo


def test_envio_do_editor_vence_arquivo_da_semente(pasta_semente, db):
    colocar(pasta_semente, "foto.png", PNG)
    documento = Documento.objects.create(nome="um-guia", titulo="Um guia", corpo="")
    Midia.objects.create(
        documento=documento,
        sorteio="a" * 32,
        nome="foto.png",
        tipo="image/png",
        tamanho=len(PNG),
    )

    corpo = documentos.para_html("![Foto](arquivo:foto)", documento=documento)

    assert f'/midia/{"a" * 32}/foto.png' in corpo
    assert "/docs/um-guia/arquivo/foto.png" not in corpo


def test_formato_desconhecido_fica_disponivel_para_download(pasta_semente, db):
    colocar(pasta_semente, "filmagem.formato", b"FORMATO-NOVO" + b"\x00" * 60)
    documento = Documento.objects.create(
        nome="um-guia",
        titulo="Um guia",
        corpo="![Filmagem](arquivo:filmagem.formato)",
        publico=True,
    )

    corpo = documentos.para_html(documento.corpo, documento=documento)
    resposta = Client().get("/docs/um-guia/arquivo/filmagem.formato")

    assert "Baixar arquivo" in corpo
    assert "<img" not in corpo
    assert "<video" not in corpo
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "application/octet-stream"
    assert resposta["Content-Disposition"].startswith("attachment;")


def test_arquivo_versionado_nao_herda_o_limite_de_upload(pasta_semente, db):
    pasta = pasta_semente / "um-guia"
    pasta.mkdir()
    caminho = pasta / "filme.formato"
    with caminho.open("wb") as destino:
        destino.write(b"FORMATO-NOVO")
        destino.seek(25 * 1024 * 1024)
        destino.write(b"fim")
    documento = Documento.objects.create(
        nome="um-guia", titulo="Um guia", corpo="", publico=True
    )

    assert documentos.endereco_do_arquivo(documento, "filme.formato") == (
        "/docs/um-guia/arquivo/filme.formato"
    )
    assert Client().get("/docs/um-guia/arquivo/filme.formato").status_code == 200
