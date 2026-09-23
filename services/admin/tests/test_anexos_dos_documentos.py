"""Anexos versionados na semente viram `/midia/` no semear, sem upload manual."""

from importlib import import_module
from pathlib import Path

import pytest
from django.db import connection
from django.db.migrations.loader import MigrationLoader

from apps.core import documentos, midia
from apps.core.models import Documento, Midia

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 60
WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20 + b"webm" + b"\x00" * 40


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
    (anexos / "clip.webm").write_bytes(WEBM + b"atualizado")
    terceiro = midia.publicar_anexos_referenciados(doc, corpo)

    assert primeiro == segundo
    assert primeiro == terceiro
    assert Midia.objects.count() == 1
    guardada = Midia.objects.get()
    assert guardada.tipo == "video/webm"
    assert guardada.tamanho == len(WEBM + b"atualizado")
    # guarda: services/admin/apps/core/midia.py:264
    assert (Path(midia.raiz()) / guardada.sorteio / guardada.nome).read_bytes() == (
        WEBM + b"atualizado"
    )


def test_publicar_anexo_preserva_outras_midias_do_volume(
    pasta_semente, disco, settings
):
    existente = Documento.objects.create(
        nome="documento-existente", titulo="Existente", corpo="", publico=True
    )
    sorteio_existente = "a" * 32
    arquivo_existente = Path(settings.MEDIA_ROOT) / sorteio_existente / "capa.png"
    arquivo_existente.parent.mkdir(parents=True)
    arquivo_existente.write_bytes(PNG)
    Midia.objects.create(
        documento=existente,
        sorteio=sorteio_existente,
        nome="capa.png",
        tipo="image/png",
        tamanho=len(PNG),
    )

    anexos = pasta_semente / "anexos" / "outro-documento"
    anexos.mkdir(parents=True)
    (anexos / "capa.png").write_bytes(PNG + b"nova")
    outro = Documento.objects.create(
        nome="outro-documento", titulo="Outro", corpo="", publico=False
    )

    midia.publicar_anexos_referenciados(outro, "![Capa](anexo:capa)")

    assert Midia.objects.count() == 2
    assert arquivo_existente.read_bytes() == PNG
    assert Midia.objects.get(documento=existente).sorteio == sorteio_existente


def test_falha_ao_copiar_preserva_arquivo_publicado(
    pasta_semente, disco, settings, monkeypatch
):
    documento = Documento.objects.create(
        nome="guia-com-arquivo", titulo="Guia", corpo="", publico=True
    )
    sorteio = midia.sorteio_deterministico(documento.nome, "capa")
    arquivo_existente = Path(settings.MEDIA_ROOT) / sorteio / "capa.png"
    arquivo_existente.parent.mkdir(parents=True)
    arquivo_existente.write_bytes(PNG)
    Midia.objects.create(
        documento=documento,
        sorteio=sorteio,
        nome="capa.png",
        tipo="image/png",
        tamanho=len(PNG),
    )
    anexos = pasta_semente / "anexos" / documento.nome
    anexos.mkdir(parents=True)
    (anexos / "capa.png").write_bytes(PNG + b"versao nova")

    def falhar_copia(**kwargs):
        raise OSError("disco indisponível")

    monkeypatch.setattr(midia.tempfile, "NamedTemporaryFile", falhar_copia)

    with pytest.raises(midia.Recusa, match="Não consegui gravar"):
        midia.publicar_anexos_referenciados(documento, "![Capa](anexo:capa)")

    assert arquivo_existente.read_bytes() == PNG
    assert Midia.objects.get(documento=documento).tamanho == len(PNG)


def test_migracao_publica_documento_historico(pasta_semente, disco, settings):
    nome = "guia-legado"
    anexos = pasta_semente / "anexos" / nome
    anexos.mkdir(parents=True)
    (anexos / "capa.png").write_bytes(PNG)
    estado = MigrationLoader(connection).project_state(
        [("core", "0026_o_crivo_explicado_so_para_administradores")]
    )
    DocumentoHistorico = estado.apps.get_model("core", "Documento")
    DocumentoHistorico.objects.create(
        nome=nome, titulo="Guia legado", corpo="![Capa](anexo:capa)", publico=True
    )
    migracao = import_module("apps.core.migrations.0027_publicar_anexos_da_semente")

    migracao.publicar_anexos(estado.apps, None)

    documento = Documento.objects.get(nome=nome)
    guardada = Midia.objects.get(documento=documento)
    arquivo_publicado = Path(settings.MEDIA_ROOT) / guardada.sorteio / guardada.nome
    # guarda: services/admin/apps/core/midia.py:287
    assert "/midia/" in documento.corpo
    assert "anexo:" not in documento.corpo
    assert arquivo_publicado.read_bytes() == PNG
