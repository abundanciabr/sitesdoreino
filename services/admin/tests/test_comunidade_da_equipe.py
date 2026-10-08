"""A vista da Comunidade abre para a equipe e não transforma falha em zero."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.core.clients import ResumoDePendencias
from apps.core.models import MembroDaEquipe


IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
EQUIPE = "livia-conta-de-teste@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    settings.URL_DE_ENTRADA = "/entrar/google"
    monkeypatch.setattr("apps.core.comunidade.site_de", lambda request: "site-teste")
    pessoa = MembroDaEquipe.objects.get(nome="Lívia")
    pessoa.email = EQUIPE
    pessoa.save()


def cliente(email=EQUIPE):
    respx.get(SESSAO).mock(return_value=httpx.Response(200, json={
        "autenticado": True, "id": "pessoa-teste", "nome_exibido": "Lívia",
        "papel": None, "email": email,
    }))
    resultado = Client()
    resultado.defaults["HTTP_COOKIE"] = COOKIE
    return resultado


@respx.mock
def test_equipe_abre_grupos_duvidas_entregas_e_reconhecimentos(monkeypatch):
    monkeypatch.setattr(
        "apps.core.comunidade.PendenciasClient.resumo",
        lambda self, fonte, site: ResumoDePendencias(3, 2),
    )
    resposta = cliente().get(reverse("comunidade_da_equipe"))
    texto = resposta.content.decode()
    assert resposta.status_code == 200
    assert "3 entregas esperando laudo" in texto
    for caminho in ("/forum/comunidade/equipe", "/cursos/plantao",
                    "/conquistas/interno/reconhecimentos"):
        assert caminho in texto
    assert "/conquistas/interno/contribuicoes" not in texto


@respx.mock
def test_fonte_muda_e_acesso_negado_nao_parecem_fila_vazia(monkeypatch):
    monkeypatch.setattr(
        "apps.core.comunidade.PendenciasClient.resumo",
        lambda self, fonte, site: ResumoDePendencias(None, acesso_negado=True),
    )
    texto = cliente().get(reverse("comunidade_da_equipe")).content.decode()
    assert "acesso entre os serviços foi recusado" in texto
    assert "Não há entregas" not in texto


@respx.mock
def test_conta_fora_da_equipe_nao_abre_a_vista(monkeypatch):
    monkeypatch.setattr(
        "apps.core.comunidade.PendenciasClient.resumo",
        lambda self, fonte, site: ResumoDePendencias(0),
    )
    assert cliente("fora@exemplo.com").get(reverse("comunidade_da_equipe")).status_code == 404


@respx.mock
def test_endereco_do_admin_abre_para_mantenedor_e_fecha_para_equipe(monkeypatch):
    monkeypatch.setattr(
        "apps.core.comunidade.PendenciasClient.resumo",
        lambda self, fonte, site: ResumoDePendencias(0),
    )
    assert cliente("dono@exemplo.com").get(reverse("comunidade_admin")).status_code == 200
    assert cliente().get(reverse("comunidade_admin")).status_code == 404
