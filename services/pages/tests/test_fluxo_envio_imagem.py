from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from apps.portfolio.models import Peca, ImagemDoPortfolio
from apps.portfolio.tasks import reconferir_os_links
from conftest import COOKIE


def foto():
    saida = BytesIO()
    Image.new("RGB", (40, 30), "blue").save(saida, format="PNG")
    return SimpleUploadedFile("modelo.png", saida.getvalue(), content_type="image/png")


@pytest.mark.django_db
def test_envio_publicacao_e_despublicacao_protegem_os_bytes(
    client, aluna, site_declarado
):
    resposta = client.post(
        "/trabalhos/guardar",
        {"imagem": foto(), "legenda": "Meu veículo"},
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    peca = Peca.objects.get()
    caminho = "/imagens/" + str(peca.imagem_enviada.pk)
    assert client.get(caminho).status_code == 404
    assert client.get(caminho, HTTP_COOKIE=COOKIE).status_code == 200
    assert (
        client.post(
            "/vitrine/publicar", {"apelido": "ana-3d"}, HTTP_COOKIE=COOKIE
        ).status_code
        == 302
    )
    assert client.get(caminho).status_code == 404
    assert client.post(
        f"/trabalhos/{peca.pk}/contexto",
        {"legenda": "Meu veículo", "mostrar_na_pagina_publica": "1"},
        HTTP_COOKIE=COOKIE,
    ).status_code == 302
    # A seleção altera o rascunho; só uma nova publicação muda a vitrine.
    assert client.get(caminho).status_code == 404
    assert client.post(
        "/vitrine/publicar", {"apelido": "ana-3d"}, HTTP_COOKIE=COOKIE
    ).status_code == 302
    assert client.get(caminho).status_code == 200
    assert peca.link in client.get("/ana-3d").content.decode()
    assert client.post("/vitrine/despublicar", HTTP_COOKIE=COOKIE).status_code == 302
    assert client.get(caminho).status_code == 404
    assert reconferir_os_links() == {"conferidas": 0, "quebradas": 0, "voltaram": 0}


@pytest.mark.django_db
def test_arquivo_falso_nao_cria_trabalho_e_mostra_o_motivo(
    client, aluna, site_declarado
):
    resposta = client.post(
        "/trabalhos/guardar",
        {
            "imagem": SimpleUploadedFile("foto.png", b"<html>nao e imagem</html>"),
            "legenda": "Meu veículo",
        },
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 422
    assert "imagem válida" in resposta.content.decode()
    assert not Peca.objects.exists()
    assert not ImagemDoPortfolio.objects.exists()


@pytest.mark.django_db
def test_sem_login_nao_guarda_imagem(client, site_declarado):
    resposta = client.post("/trabalhos/guardar", {"imagem": foto()})
    assert "Entre para ver o seu portfólio" in resposta.content.decode()
    assert not Peca.objects.exists()


@pytest.mark.django_db(transaction=True)
def test_imagem_publicada_abre_no_asgi_com_prefixo_real(settings, site_declarado):
    from asgiref.sync import async_to_sync
    from django.test import AsyncClient
    from apps.portfolio import imagens, vitrine
    from apps.core.views import site_atual

    settings.FORCE_SCRIPT_NAME = "/portfolio"
    peca = imagens.guardar(
        foto(),
        site_id=site_atual(),
        aluno_id="p_ana",
        legenda="Veículo",
        base_url="https://testserver",
    )
    peca.mostrar_na_pagina_publica = True
    peca.save(update_fields=["mostrar_na_pagina_publica"])
    vitrine.publicar(site_id=site_atual(), aluno_id="p_ana", texto="ana-3d")
    caminho = "/portfolio/imagens/" + str(peca.imagem_enviada.pk)
    resposta = async_to_sync(AsyncClient().get)(caminho)
    assert resposta.status_code == 200
    assert resposta["Content-Type"] == "image/webp"
    assert resposta["Cache-Control"] == "no-store"
    assert peca.link == "https://testserver" + caminho
