import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse

from apps.core.plano_praticas_3d import PLANO
from apps.cursos.models import ItemDePlanoDeProducao, Progresso
from tests.conftest import ANA, COOKIE, dublar_matricula, dublar_sessao

pytestmark = pytest.mark.django_db


def equipe(monkeypatch, rede):
    monkeypatch.setenv("ADMIN_EMAILS", ANA["email"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")


def test_visitante_le_o_plano_sem_criar_progresso(env_dos_pares, client):
    resposta = client.get(reverse("plano-praticas-3d"))
    assert resposta.status_code == 200
    assert b"modo de leitura" in resposta.content
    assert b"<iframe" not in resposta.content
    assert Progresso.objects.count() == ItemDePlanoDeProducao.objects.count() == 0


def test_visitante_nao_muda_checklist(env_dos_pares, client):
    resposta = client.post(reverse("plano-praticas-3d"), {"item": "espada-blender", "feito": "sim"})
    assert resposta.status_code == 403
    assert ItemDePlanoDeProducao.objects.count() == 0


def test_aluno_nao_muda_checklist(env_dos_pares, rede, client, monkeypatch):
    monkeypatch.delenv("CURSOS_PROFESSORES", raising=False)
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    resposta = client.post(reverse("plano-praticas-3d"), {"item": "espada-blender", "feito": "sim"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
    assert ItemDePlanoDeProducao.objects.count() == 0


def test_equipe_salva_recupera_e_atualiza_sem_duplicar(env_dos_pares, rede, monkeypatch, client):
    equipe(monkeypatch, rede)
    url = reverse("plano-praticas-3d")
    resposta = client.post(url, {"item": "espada-blender", "feito": "sim", "nota": "Prova https://meshcraft.top/"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 302
    assert resposta.url.endswith("?salvo=1#espada")
    assert ItemDePlanoDeProducao.objects.get(chave="espada-blender").feito
    # Uma nova sessão sem o cookie da equipe ainda lê a marcação persistida.
    assert b"Prova https://meshcraft.top/" in Client().get(url).content
    client.post(url, {"item": "espada-blender", "nota": "Retomado"}, HTTP_COOKIE=COOKIE)
    assert ItemDePlanoDeProducao.objects.count() == 1
    assert not ItemDePlanoDeProducao.objects.get().feito
    assert Progresso.objects.count() == 0


def test_um_item_nao_sobrescreve_o_outro_nem_outro_site(env_dos_pares, rede, monkeypatch, client):
    equipe(monkeypatch, rede)
    outro = ItemDePlanoDeProducao.objects.create(site_id="escola-b", plano=PLANO, chave="espada-blender", feito=True, nota="Nota de outro site")
    url = reverse("plano-praticas-3d")
    for chave in ["espada-blender", "espada-partes"]:
        client.post(url, {"item": chave, "feito": "sim", "nota": chave}, HTTP_COOKIE=COOKIE)
    assert ItemDePlanoDeProducao.objects.filter(site_id="escola-a", feito=True).count() == 2
    outro.refresh_from_db()
    assert outro.nota == "Nota de outro site"
    assert b"Nota de outro site" not in client.get(url).content


def test_notas_sao_texto_sem_executar_html(env_dos_pares, rede, monkeypatch, client):
    equipe(monkeypatch, rede)
    url = reverse("plano-praticas-3d")
    client.post(url, {"item": "espada-blender", "nota": "<script>alert(1)</script>"}, HTTP_COOKIE=COOKIE)
    html = Client().get(url).content.decode()
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_post_com_item_desconhecido_nao_grava(env_dos_pares, rede, monkeypatch, client):
    equipe(monkeypatch, rede)
    resposta = client.post(reverse("plano-praticas-3d"), {"item": "qualquer", "feito": "sim"}, HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 404
    assert ItemDePlanoDeProducao.objects.count() == 0


def test_edicao_exige_csrf_e_grava_com_token(env_dos_pares, rede, monkeypatch):
    equipe(monkeypatch, rede)
    client = Client(enforce_csrf_checks=True)
    url = reverse("plano-praticas-3d")
    assert client.post(url, {"item": "espada-blender", "feito": "sim"}, HTTP_COOKIE=COOKIE).status_code == 403
    client.cookies["meshcraft_sessao"] = "cookie-opaco-de-ana"
    assert client.get(url).status_code == 200
    token = client.cookies[settings.CSRF_COOKIE_NAME].value
    resposta = client.post(url, {"item": "espada-blender", "feito": "sim", "csrfmiddlewaretoken": token})
    assert resposta.status_code == 302
    assert ItemDePlanoDeProducao.objects.get().feito
