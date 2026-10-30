import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from apps.core.models import Administrador, MembroDaEquipe
from apps.auditoria.models import Registro

@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    settings.ADMIN_EMAILS = "dono@exemplo.com"
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "teste")

def cliente(email):
    respx.get("http://identidade:8000/interno/sessao/completa").mock(return_value=httpx.Response(200, json={"autenticado": True, "id": "teste", "nome_exibido": "Teste", "email": email}))
    c = Client()
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    return c

def pessoa(**kwargs):
    return MembroDaEquipe.objects.create(nome="Pessoa de teste", email="equipe@exemplo.com", **kwargs)

@respx.mock
def test_promove_persiste_e_autoriza():
    p = pessoa()
    c = cliente("dono@exemplo.com")
    url = reverse("equipe_tornar_administrador", args=[p.pk])
    assert b"Tornar administrador" in c.get(reverse("pessoas_da_equipe")).content
    assert b"Tornar administrador" in c.get(reverse("ficha_da_pessoa", args=[p.pk])).content
    assert c.get(url).status_code == 405
    assert c.post(url, {"email": "intruso@exemplo.com"}).status_code == 302
    assert Administrador.objects.get(email=p.email).ativo
    assert not Administrador.objects.filter(email="intruso@exemplo.com").exists()
    assert c.post(url).status_code == 302
    assert Registro.objects.filter(acao=Registro.PROMOVER, alvo=p.email).count() == 1
    assert b"Administrador do site" in c.get(reverse("pessoas_da_equipe")).content
    membro = cliente(p.email)
    assert membro.get(reverse("pessoas_da_equipe")).status_code == 200

@respx.mock
@pytest.mark.parametrize("estado", ["inativo", "sem_email", "pendente"])
def test_exige_pessoa_ativa_email_conferido(estado):
    p = pessoa(ativo=estado != "inativo", email_a_conferir=estado == "pendente")
    if estado == "sem_email":
        p.email = ""
        p.save()
    assert cliente("dono@exemplo.com").post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 400
    assert not Administrador.objects.exists()

@respx.mock
@pytest.mark.parametrize("quem", ["equipe", "admin"])
def test_so_mantenedor_promove(quem):
    p = pessoa()
    if quem == "admin":
        Administrador.objects.create(email=p.email)
    c = cliente(p.email)
    assert c.post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 403
    assert not Registro.objects.filter(acao=Registro.PROMOVER).exists()

@respx.mock
def test_reativa_sem_apagar_historico():
    p = pessoa()
    admin = Administrador.objects.create(email=p.email, ativo=False)
    c = cliente("dono@exemplo.com")
    assert c.post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 302
    admin.refresh_from_db()
    assert admin.ativo
    assert Administrador.objects.filter(email=p.email).count() == 1

@respx.mock
def test_csrf():
    p = pessoa()
    cliente("dono@exemplo.com")
    c = Client(enforce_csrf_checks=True)
    c.defaults["HTTP_COOKIE"] = "meshcraft_sessao=teste"
    assert c.post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 403
    assert not Administrador.objects.exists()


def test_robo_nao_promove():
    import io
    from django.core.management import call_command
    p = pessoa()
    saida = io.StringIO()
    call_command("conta_do_robo", "emitir", stdout=saida, stderr=io.StringIO())
    c = Client(enforce_csrf_checks=True, HTTP_AUTHORIZATION="Robo " + saida.getvalue().strip())
    assert c.post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 403
    assert not Administrador.objects.exists()


def test_anonimo_nao_promove():
    p = pessoa()
    assert Client().post(reverse("equipe_tornar_administrador", args=[p.pk])).status_code == 302
    assert not Administrador.objects.exists()
