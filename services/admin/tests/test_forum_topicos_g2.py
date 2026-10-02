"""Conversas da escola são rascunhadas antes de aparecer no fórum."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse


IDENTIDADE = "http://identidade:8000/interno/sessao/completa"
CATALOGO = "http://catalogo:8000/api/catalogo/sites/by-host/testserver"
EDITOR = "http://forum:8000/interno/editor"
RASCUNHO_ID = "11111111-1111-4111-8111-111111111111"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "identidade-teste")
    monkeypatch.setenv("CATALOGO_API_URL", "http://catalogo:8000/api/catalogo")
    monkeypatch.setenv("TOKEN_CATALOGO", "catalogo-teste")
    monkeypatch.setenv("FORUM_API_URL", "http://forum:8000/interno")
    monkeypatch.setenv("TOKEN_FORUM", "forum-teste")


def _cliente():
    respx.get(IDENTIDADE).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "dono-id",
                "nome_exibido": "Dono",
                "papel": None,
                "email": "dono@exemplo.com",
            },
        )
    )
    respx.get(CATALOGO).mock(
        return_value=httpx.Response(
            200, json={"id": "site-teste", "host": "testserver", "menu": {}}
        )
    )
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return cliente


@respx.mock
def test_conversa_nova_so_aparece_depois_de_publicar():
    cliente = _cliente()
    areas = respx.get(EDITOR + "/areas").mock(
        return_value=httpx.Response(
            200, json={"areas": [{"slug": "duvidas", "nome": "Dúvidas"}]}
        )
    )
    listar = respx.get(EDITOR + "/topicos").mock(
        return_value=httpx.Response(200, json={"topicos": []})
    )
    criar = respx.post(EDITOR + "/topicos/rascunho").mock(
        return_value=httpx.Response(201, json={"rascunho_id": RASCUNHO_ID})
    )
    detalhe = {
        "rascunho_id": RASCUNHO_ID,
        "topico_id": None,
        "area_slug": "duvidas",
        "titulo": "Primeira conversa",
        "texto": "Uma pergunta",
        "rascunho": True,
    }
    buscar = respx.get(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}").mock(
        return_value=httpx.Response(200, json=detalhe)
    )
    salvar = respx.put(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}").mock(
        return_value=httpx.Response(200, json=detalhe)
    )
    publicar = respx.post(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}/publicar").mock(
        return_value=httpx.Response(200, json={**detalhe, "rascunho": False})
    )

    assert cliente.get(reverse("forum_topicos")).status_code == 200
    assert listar.called
    assert listar.calls.last.request.headers["authorization"] == "Bearer forum-teste"
    assert cliente.get(reverse("forum_topico_novo")).status_code == 200
    assert areas.called
    enviado = {
        "area_slug": "duvidas",
        "titulo": "Primeira conversa",
        "texto": "Uma pergunta",
    }
    resposta = cliente.post(reverse("forum_topico_criar"), enviado)
    assert resposta.status_code == 302
    assert criar.calls.last.request.headers["authorization"] == "Bearer forum-teste"
    assert not publicar.called

    editar_url = reverse("forum_topico_editar", kwargs={"rascunho_id": RASCUNHO_ID})
    pagina = cliente.get(editar_url)
    assert pagina.status_code == 200
    assert buscar.called
    assert "Prévia privada" in pagina.content.decode()
    assert (
        cliente.post(
            reverse("forum_topico_salvar", kwargs={"rascunho_id": RASCUNHO_ID}), enviado
        ).status_code
        == 302
    )
    assert salvar.called
    assert not publicar.called

    assert (
        cliente.post(
            reverse("forum_topico_publicar", kwargs={"rascunho_id": RASCUNHO_ID})
        ).status_code
        == 302
    )
    assert publicar.called


@respx.mock
def test_conversa_existente_abre_rascunho_sem_publicar():
    cliente = _cliente()
    abrir = respx.post(EDITOR + "/topicos/7/rascunho").mock(
        return_value=httpx.Response(201, json={"rascunho_id": RASCUNHO_ID})
    )
    resposta = cliente.post(
        reverse("forum_topico_abrir_edicao", kwargs={"topico_id": 7})
    )
    assert resposta.status_code == 302
    assert RASCUNHO_ID in resposta["Location"]
    assert abrir.called


@respx.mock
def test_falha_de_publicacao_mantem_previa_e_acao_de_corrigir():
    cliente = _cliente()
    respx.get(EDITOR + "/areas").mock(
        return_value=httpx.Response(
            200, json={"areas": [{"slug": "duvidas", "nome": "Dúvidas"}]}
        )
    )
    respx.get(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}").mock(
        return_value=httpx.Response(
            200,
            json={
                "rascunho_id": RASCUNHO_ID,
                "area_slug": "duvidas",
                "titulo": "Uma pergunta",
                "texto": "Texto",
            },
        )
    )
    respx.post(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}/publicar").mock(
        return_value=httpx.Response(422, json={"detail": "invalido"})
    )
    resposta = cliente.post(
        reverse("forum_topico_publicar", kwargs={"rascunho_id": RASCUNHO_ID})
    )
    assert resposta.status_code == 422
    assert "Uma pergunta" in resposta.content.decode()
    assert (
        reverse("forum_topico_salvar", kwargs={"rascunho_id": RASCUNHO_ID})
        in resposta.content.decode()
    )


@respx.mock
def test_sem_sessao_nao_edita_nem_publica_conversas():
    cliente = Client()
    assert cliente.get(reverse("forum_topicos")).status_code in (302, 404)
    assert cliente.post(
        reverse("forum_topico_publicar", kwargs={"rascunho_id": RASCUNHO_ID})
    ).status_code in (302, 404)


@pytest.mark.parametrize("novo", [True, False])
@pytest.mark.parametrize("falha", ["salvar", "publicar", None])
@respx.mock
def test_salvar_e_publicar_conversa_em_um_clique(novo, falha):
    cliente = _cliente()
    respx.get(EDITOR + "/areas").mock(
        return_value=httpx.Response(200, json={"areas": [{"slug": "duvidas", "nome": "Dúvidas"}]})
    )
    caminho = (
        reverse("forum_topico_criar") if novo else
        reverse("forum_topico_salvar", kwargs={"rascunho_id": RASCUNHO_ID})
    )
    salvar = (
        respx.post(EDITOR + "/topicos/rascunho") if novo else
        respx.put(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}")
    ).mock(return_value=httpx.Response(
        422 if falha == "salvar" else 201,
        json={} if falha == "salvar" else {"rascunho_id": RASCUNHO_ID},
    ))
    publicar = respx.post(EDITOR + f"/topicos/rascunho/{RASCUNHO_ID}/publicar").mock(
        return_value=httpx.Response(422 if falha == "publicar" else 200, json={})
    )
    resposta = cliente.post(caminho, {
        "area_slug": "duvidas", "titulo": "Título novo", "texto": "Texto novo", "acao": "publicar",
    })
    assert salvar.call_count == 1
    assert publicar.call_count == (0 if falha == "salvar" else 1)
    assert resposta.status_code == (422 if falha else 302)
    if falha:
        assert "Título novo" in resposta.content.decode()
        assert "Texto novo" in resposta.content.decode()
    if falha == "publicar":
        assert RASCUNHO_ID in resposta.content.decode()
