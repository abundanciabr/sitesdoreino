"""Anexos versionados na semente viram `/midia/` no semear, sem upload manual."""

from pathlib import Path

import pytest

from apps.core import documentos, midia
from apps.core.models import Documento, Midia

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60
WEBM = b"\x1aE\xdf\xa3" + b"\x00" * 60


@pytest.fixture(autouse=True)
def disco(tmp_path, settings):
    settings.MEDIA_ROOT = str(tmp_path / "midia")


@pytest.fixture(autouse=True)
def so_este_documento(db):
    Documento.objects.all().delete()
    Midia.objects.all().delete()


@pytest.fixture
def pasta_semente(tmp_path, monkeypatch):
    raiz = tmp_path / "documentos"
    raiz.mkdir()
    monkeypatch.setattr(documentos, "CANDIDATOS", (raiz,))
    return raiz


def test_sorteio_deterministico_e_estavel():
    a = midia.sorteio_deterministico("guia", "capa")
    b = midia.sorteio_deterministico("guia", "capa")
    c = midia.sorteio_deterministico("guia", "outra")
    assert a == b
    assert a != c
    assert len(a) == 32


def test_semear_publica_anexo_e_grava_corpo_com_midia(pasta_semente, disco, settings):
    nome = "guia-com-midia"
    (pasta_semente / f"{nome}.md").write_text(
        "---\ntitulo: Guia com mídia\npublico: false\n---\n\n"
        "![Capa do guia](anexo:capa)\n",
        encoding="utf-8",
    )
    anexos = pasta_semente / "anexos" / nome
    anexos.mkdir(parents=True)
    (anexos / "capa.png").write_bytes(PNG)

    assert documentos.semear_documento(Documento, nome) is True

    doc = Documento.objects.get(nome=nome)
    assert "anexo:" not in doc.corpo
    assert "/midia/" in doc.corpo
    guardada = Midia.objects.get()
    assert guardada.enviado_por == midia.EMAIL_DA_SEMENTE
    assert guardada.sorteio == midia.sorteio_deterministico(nome, "capa")
    caminho = Path(settings.MEDIA_ROOT) / guardada.sorteio / guardada.nome
    assert caminho.read_bytes() == PNG


def test_semear_de_novo_nao_sobrescreve_documento_existente(pasta_semente):
    nome = "guia-idempotente"
    (pasta_semente / f"{nome}.md").write_text(
        "---\ntitulo: Guia\npublico: false\n---\n\n![x](anexo:capa)\n",
        encoding="utf-8",
    )
    Documento.objects.create(
        nome=nome, titulo="Guia", corpo="corpo do mantenedor", publico=False
    )

    assert documentos.semear_documento(Documento, nome) is False
    assert Documento.objects.get().corpo == "corpo do mantenedor"
    assert Midia.objects.count() == 0


def test_para_html_trata_webm_como_video():
    endereco = f"/midia/{'a' * 32}/demo.webm"
    html_ = documentos.para_html(f"![Demo]({endereco})")
    assert "<video controls" in html_
    assert endereco in html_


def test_publicar_anexos_idempotente_atualiza_arquivo(pasta_semente, disco):
    nome = "guia-atualizado"
    doc = Documento.objects.create(nome=nome, titulo="Guia", corpo="", publico=False)
    anexos = pasta_semente / "anexos" / nome
    anexos.mkdir(parents=True)
    (anexos / "clip.webm").write_bytes(WEBM)
    corpo = "![Clip](anexo:clip)\n"

    primeiro = midia.publicar_anexos_referenciados(doc, corpo)
    segundo = midia.publicar_anexos_referenciados(doc, corpo)

    assert primeiro == segundo
    assert Midia.objects.count() == 1
    assert Midia.objects.get().tipo == "video/webm"
