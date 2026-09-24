import httpx

from tests.conftest import CATALOGO, HOST_A, HOST_MESH, SITE_A, SITE_MESH, caminho_mesh
from tests.test_pagina_vista import envelope, fio


def publicar(rede, corpo, status=200, site_id=SITE_A["id"]):
    rede.get(f"{CATALOGO}/sites/{site_id}/paginas/flp-0").mock(
        return_value=httpx.Response(status, json=corpo)
    )


def pagina():
    return {
        "id": "flp-publicada",
        "site_id": SITE_A["id"],
        "slug": "flp-0",
        "tipo": "flp",
        "version": 4,
        "offer_slug": "",
        "published_at": "2026-09-24T12:00:00-03:00",
        "secoes": [
            {
                "nome": "abertura",
                "ordem": 0,
                "slots": {
                    "headline": "Comece seu negócio digital",
                    "subheadline": "Um passo de cada vez",
                    "cta_texto": "Começar agora",
                    "cta_destino": "/cadastro?origem=flp",
                },
            },
            {
                "nome": "entrega",
                "ordem": 1,
                "slots": {"headline": "O que você recebe", "dashboard": "Seu painel"},
            },
        ],
    }


def test_flp_publicada_desenha_copy_utm_e_mede_versao(client, rede, fio):
    publicar(rede, pagina())

    resposta = client.get(
        "/flp-0", {"utm_source": "instagram", "utm_medium": "cpc"}, HTTP_HOST=HOST_A
    )

    corpo = resposta.content.decode()
    assert resposta.status_code == 200
    assert corpo.index("Comece seu negócio digital") < corpo.index("O que você recebe")
    assert "Seu painel" in corpo
    assert (
        'href="/cadastro?origem=flp&amp;utm_source=instagram&amp;utm_medium=cpc"'
        in corpo
    )
    assert envelope(fio)[1]["data"]["pagina_slug"] == "flp-0"
    assert envelope(fio)[1]["data"]["pagina_version"] == 4


def test_flp_sem_publicacao_e_404(client, rede):
    publicar(rede, None, status=404)

    resposta = client.get("/flp-0", HTTP_HOST=HOST_A)

    assert resposta.status_code == 404
    assert "ainda não foi publicada" in resposta.content.decode()


def test_flp_com_catalogo_mudo_ou_corpo_de_outro_tipo_e_503(client, rede):
    rota = rede.get(f"{CATALOGO}/sites/{SITE_A['id']}/paginas/flp-0")
    rota.mock(side_effect=httpx.ConnectError("sem conexão"))
    resposta = client.get("/flp-0", HTTP_HOST=HOST_A)
    assert resposta.status_code == 503
    assert resposta["Retry-After"] == "30"
    assert "Atualize" in resposta.content.decode()

    errado = pagina()
    errado["tipo"] = "oferta"
    rota.mock(return_value=httpx.Response(200, json=errado))
    assert client.get("/flp-0", HTTP_HOST=HOST_A).status_code == 503


def test_flp_nao_cria_link_de_destino_inseguro(client, rede):
    corpo = pagina()
    corpo["secoes"][0]["slots"]["cta_destino"] = "javascript:alert(1)"
    publicar(rede, corpo)

    resposta = client.get("/flp-0", HTTP_HOST=HOST_A)

    assert resposta.status_code == 200
    assert "javascript:" not in resposta.content.decode()


def test_flp_sem_secao_util_e_503_em_vez_de_tela_vazia(client, rede):
    corpo = pagina()
    corpo["secoes"] = [{"nome": "abertura", "ordem": 0, "slots": {}}]
    publicar(rede, corpo)

    resposta = client.get("/flp-0", HTTP_HOST=HOST_A)

    assert resposta.status_code == 503
    assert resposta["Retry-After"] == "30"


def test_flp_respeita_caminho_localizado_do_site(client, rede):
    publicar(rede, pagina(), site_id=SITE_MESH["id"])

    resposta = client.get(
        caminho_mesh("pt-br", "/primeiros-dolares-com-roblox"),
        HTTP_HOST=HOST_MESH,
    )

    assert resposta.status_code == 200
    assert "inscrições não estão disponíveis" in resposta.content.decode()
    assert "Comece seu negócio digital" not in resposta.content.decode()
