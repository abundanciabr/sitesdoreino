"""A mudança de endereço preserva links e mantém separadas as áreas privadas."""

import httpx
import pytest
from asgiref.sync import async_to_sync
from django.test import AsyncClient

from apps.core.enderecos import RESERVADOS
from apps.portfolio import vitrine
from config.asgi import application


@pytest.mark.parametrize(
    "origem,destino",
    [
        ("/pages/", "/portfolio/"),
        ("/pages/pecas?ordem=1", "/portfolio/trabalhos?ordem=1"),
        ("/pages/pecas/guardar", "/portfolio/trabalhos/guardar"),
        ("/estudio/ana-3d", "/portfolio/ana-3d"),
    ],
)
def test_links_antigos_preservam_destino_e_metodo(origem, destino):
    async def consultar():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application),
            base_url="https://testserver",
        ) as cliente:
            return await cliente.post(origem, content=b"legenda=meu-trabalho")

    resposta = async_to_sync(consultar)()
    assert resposta.status_code == 308
    assert resposta.headers["location"] == destino


@pytest.mark.django_db(transaction=True)
def test_publico_com_prefixo_real_abre_sem_login(
    settings, criar_portfolio, site_declarado
):
    settings.FORCE_SCRIPT_NAME = "/portfolio"
    criar_portfolio("p_ana", apelido="ana-3d", publicada=True)
    resposta = async_to_sync(AsyncClient().get)("/portfolio/ana-3d")
    assert resposta.status_code == 200
    assert b"ana-3d" in resposta.content
    assert resposta["Cache-Control"] == "no-store"


def test_tela_de_trabalhos_permanece_privada(client, settings):
    settings.FORCE_SCRIPT_NAME = "/portfolio"
    resposta = client.get("/trabalhos")
    assert b'name="imagem"' not in resposta.content
    assert "entrar" in resposta.content.decode().lower()


@pytest.mark.django_db
@pytest.mark.parametrize("apelido", sorted(RESERVADOS))
def test_apelido_nao_toma_endereco_de_uma_tela(apelido):
    with pytest.raises(vitrine.VitrineRecusada, match="usado por uma página"):
        vitrine.publicar(site_id="escola-a", aluno_id="p_ana", texto=apelido)


def test_nome_e_destino_publico():
    assert vitrine.endereco("ana-3d") == "/portfolio/ana-3d"
