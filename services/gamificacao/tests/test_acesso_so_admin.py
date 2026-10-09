"""/conquistas/ só para administradores durante a atualização."""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.gamificacao.models import VersaoDoRecebimento

pytestmark = pytest.mark.django_db
AVISO = "Esta página está sendo atualizada. Em breve teremos novidades."
ID = "http://identidade:8000/interno"
ADM = "http://admin:8000/interno"


@pytest.fixture(autouse=True)
def amb(monkeypatch):
    monkeypatch.setenv("SITE_ID", "site-de-teste")
    monkeypatch.setenv("IDENTIDADE_API_URL", ID)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "t")
    monkeypatch.setenv("ADMIN_API_URL", ADM)
    monkeypatch.setenv("ADMIN_API_TOKEN", "t")
    monkeypatch.setenv("IDS_DA_EQUIPE", "")


def como(monkeypatch, pessoa):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa)


def get(url):
    c = Client()
    c.cookies["sessao"] = "x"
    return c.get(url)


def test_visitante_ve_o_aviso(monkeypatch):
    como(monkeypatch, None)
    for nome in ("base", "medalhas"):
        r = get(reverse(nome))
        assert r.status_code == 200 and AVISO in r.content.decode()
        assert "no-cache" in r["Cache-Control"] or "no-store" in r["Cache-Control"]


def test_aluno_nao_admin_ve_so_o_aviso(monkeypatch):
    como(monkeypatch, "pes-1")
    with respx.mock:
        respx.get(f"{ID}/sessao/completa").respond(json={"autenticado": True, "email": "a@x.com"})
        respx.post(f"{ADM}/administradores/consultar").respond(json={"e_administrador": False})
        corpo = get(reverse("base")).content.decode()
    assert AVISO in corpo
    for proibido in ("jornada", "Medalha", "medalha", "escada", "Entrar na escola"):
        assert proibido not in corpo


def test_admin_pela_equipe_ve_a_pagina(monkeypatch):
    como(monkeypatch, "pes-1")
    monkeypatch.setenv("IDS_DA_EQUIPE", "pes-1")
    assert AVISO not in get(reverse("base")).content.decode()


def test_admin_pelo_email_ve_a_pagina(monkeypatch):
    como(monkeypatch, "pes-1")
    with respx.mock:
        respx.get(f"{ID}/sessao/completa").respond(json={"autenticado": True, "email": "a@x.com"})
        rota = respx.post(f"{ADM}/administradores/consultar").respond(json={"e_administrador": True})
        r = get(reverse("medalhas"))
    assert r.status_code == 200 and AVISO not in r.content.decode()
    assert rota.call_count == 1


def test_admin_fora_do_ar_ou_estranha_vira_aviso_sem_500(monkeypatch):
    como(monkeypatch, "pes-1")
    for resposta in (httpx.ConnectTimeout("t"), httpx.Response(500), httpx.Response(200, text="<html>")):
        with respx.mock:
            respx.get(f"{ID}/sessao/completa").respond(json={"autenticado": True, "email": "a@x.com"})
            rota = respx.post(f"{ADM}/administradores/consultar")
            if isinstance(resposta, Exception):
                rota.mock(side_effect=resposta)
            else:
                rota.mock(return_value=resposta)
            r = get(reverse("base"))
        assert r.status_code == 200 and AVISO in r.content.decode()


def test_sem_env_da_admin_vira_aviso(monkeypatch):
    como(monkeypatch, "pes-1")
    monkeypatch.delenv("ADMIN_API_URL")
    monkeypatch.delenv("ADMIN_API_TOKEN")
    assert AVISO in get(reverse("base")).content.decode()


def test_post_salvar_de_nao_admin_nao_grava(monkeypatch):
    como(monkeypatch, "pes-1")
    from apps.gamificacao.models import JornadaPessoal
    r = Client().post(reverse("salvar-jornada"), {"acao": "salvar", "meta": "500"})
    assert r.status_code == 303 and r["Location"] == reverse("base")
    assert not JornadaPessoal.objects.exists()


def test_print_404_para_nao_admin_e_200_para_admin(monkeypatch):
    from tests.test_prints_recebimentos import enviar
    from tests.test_faixas_pagina import P
    enviar()
    url = reverse("print-recebimento", args=[VersaoDoRecebimento.objects.get().pk])
    como(monkeypatch, P)
    assert Client().get(url).status_code == 404
    monkeypatch.setenv("IDS_DA_EQUIPE", P)
    assert Client().get(url).status_code == 200


def test_healthz_e_api_continuam_abertos(monkeypatch):
    como(monkeypatch, None)
    assert Client().get("/healthz").status_code == 200
