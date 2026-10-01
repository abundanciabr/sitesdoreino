from io import BytesIO
from unittest.mock import patch
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from PIL import Image

from apps.portfolio.imagens import ImagemRecusada, _normalizar, guardar, servir_imagem
from apps.portfolio.models import ImagemDoPortfolio, Portfolio


def arquivo(formato="PNG", tamanho=(40, 30)):
    saida = BytesIO()
    Image.new("RGB", tamanho, "red").save(saida, format=formato)
    return SimpleUploadedFile("foto.bin", saida.getvalue())


@pytest.mark.parametrize("formato", ["JPEG", "PNG", "WEBP"])
def test_formatos_validos_viram_webp_sem_metadados(formato):
    dados, largura, altura = _normalizar(arquivo(formato))
    with Image.open(BytesIO(dados)) as imagem:
        assert imagem.format == "WEBP"
        assert imagem.size == (largura, altura) == (40, 30)
        assert not imagem.getexif()


def test_arquivo_disfarcado_e_animacao_sao_recusados():
    with pytest.raises(ImagemRecusada):
        _normalizar(SimpleUploadedFile("foto.png", b"<svg>falso</svg>"))
    saida = BytesIO()
    primeira = Image.new("RGB", (10, 10), "red")
    primeira.save(
        saida,
        format="WEBP",
        save_all=True,
        append_images=[Image.new("RGB", (10, 10), "blue")],
        duration=100,
    )
    with pytest.raises(ImagemRecusada):
        _normalizar(SimpleUploadedFile("animado.webp", saida.getvalue()))


def test_png_em_paleta_preserva_transparencia():
    imagem = Image.new("P", (2, 2), 0)
    imagem.putpalette([255, 0, 0, 0, 0, 255] + [0] * 762)
    imagem.info["transparency"] = 0
    saida = BytesIO()
    imagem.save(saida, format="PNG")
    dados, _, _ = _normalizar(SimpleUploadedFile("paleta.png", saida.getvalue()))
    with Image.open(BytesIO(dados)) as final:
        assert final.convert("RGBA").getpixel((0, 0))[3] == 0


def test_imagem_com_pixels_demais_e_recusada():
    with pytest.raises(ImagemRecusada, match="20 milhões"):
        _normalizar(arquivo(tamanho=(5000, 5000)))


def test_leitura_em_chunks_recusa_mais_de_cinco_mib_mesmo_com_size_falso():
    class Mentiroso:
        size = 1

        def chunks(self):
            yield b"x" * (5 * 1024 * 1024)
            yield b"y"

    with pytest.raises(ImagemRecusada, match="5 MiB"):
        _normalizar(Mentiroso())


@pytest.mark.django_db
def test_guardar_peca_e_imagem_no_mesmo_portfolio():
    peca = guardar(
        arquivo(),
        site_id="escola-a",
        aluno_id="ana",
        legenda=" Minha obra ",
        base_url="https://site.test",
    )
    imagem = peca.imagem_enviada
    assert peca.link == f"https://site.test/portfolio/imagens/{imagem.id}"
    assert peca.legenda == "Minha obra"
    assert peca.estado_do_link == "respondendo"
    assert peca.conferido_em is not None
    assert (imagem.largura, imagem.altura, imagem.tamanho) == (
        40,
        30,
        len(imagem.bytes),
    )
    assert (
        guardar(
            arquivo(),
            site_id="escola-a",
            aluno_id="ana",
            legenda="",
            base_url="https://site.test",
        ).ordem
        == 2
    )


@pytest.mark.django_db
def test_quota_impede_gravacao_parcial():
    peca = guardar(
        arquivo(),
        site_id="escola-a",
        aluno_id="ana",
        legenda="",
        base_url="https://site.test",
    )
    with patch("apps.portfolio.imagens.LIMITE_PORTFOLIO", peca.imagem_enviada.tamanho):
        with pytest.raises(ImagemRecusada, match="50 MiB"):
            guardar(
                arquivo(),
                site_id="escola-a",
                aluno_id="ana",
                legenda="",
                base_url="https://site.test",
            )
    assert ImagemDoPortfolio.objects.count() == 1


@pytest.mark.django_db
def test_publica_e_privada_outra_escola_e_despublicada(monkeypatch):
    monkeypatch.setenv("SITE_ID", "escola-a")
    peca = guardar(
        arquivo(),
        site_id="escola-a",
        aluno_id="ana",
        legenda="",
        base_url="https://site.test",
    )
    imagem = peca.imagem_enviada
    pedido = RequestFactory().get("/portfolio/imagens/" + str(imagem.id))
    assert servir_imagem(pedido, imagem.id).status_code == 404
    portfolio = peca.portfolio
    portfolio.apelido = "ana"
    portfolio.vitrine_publicada = True
    from django.utils import timezone

    portfolio.publicada_em = timezone.now()
    portfolio.save()
    resposta = servir_imagem(pedido, imagem.id)
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/webp"
    assert resposta["Cache-Control"] == "no-store"
    assert resposta["X-Content-Type-Options"] == "nosniff"
    monkeypatch.setenv("SITE_ID", "escola-b")
    assert servir_imagem(pedido, imagem.id).status_code == 404
    monkeypatch.setenv("SITE_ID", "escola-a")
    portfolio.vitrine_publicada = False
    portfolio.publicada_em = None
    portfolio.save()
    assert servir_imagem(pedido, imagem.id).status_code == 404
    assert servir_imagem(pedido, uuid.uuid4()).status_code == 404


@pytest.mark.django_db
def test_privada_so_dono_com_matricula_ativa_ou_equipe(monkeypatch):
    monkeypatch.setenv("SITE_ID", "escola-a")
    imagem = guardar(
        arquivo(),
        site_id="escola-a",
        aluno_id="ana",
        legenda="",
        base_url="https://site.test",
    ).imagem_enviada
    pedido = RequestFactory().get(
        "/portfolio/imagens/" + str(imagem.id), HTTP_COOKIE="sessao=x"
    )
    with patch(
        "apps.core.clients.IdentidadeClient.sessao_completa",
        return_value={"autenticado": True, "id": "outro", "email": "outro@test"},
    ), patch("apps.core.equipe.e_da_equipe", return_value=False):
        assert servir_imagem(pedido, imagem.id).status_code == 404
    with patch(
        "apps.core.clients.IdentidadeClient.sessao_completa",
        return_value={"autenticado": True, "id": "ana", "email": "ana@test"},
    ), patch("apps.core.clients.AlunosClient.categoria_de", return_value="aluno"):
        assert servir_imagem(pedido, imagem.id).status_code == 200
    with patch(
        "apps.core.clients.IdentidadeClient.sessao_completa",
        return_value={"autenticado": True, "id": "equipe", "email": "prof@test"},
    ), patch("apps.core.equipe.e_da_equipe", return_value=True):
        assert servir_imagem(pedido, imagem.id).status_code == 200
