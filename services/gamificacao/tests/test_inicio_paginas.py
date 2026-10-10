"""O começo ocupa três páginas privadas; a Base só aponta a retomada."""

import re
from html import unescape

import pytest
from django.test import Client, override_settings
from django.urls import get_script_prefix, reverse, set_script_prefix

from apps.gamificacao.models import JornadaPessoal


pytestmark = pytest.mark.django_db
SITE, P = "site-paginas", "aluna-paginas"
ETAPAS = ("inicio-motivo", "inicio-objetivo", "inicio-item")


@pytest.fixture(autouse=True)
def conta(monkeypatch):
    monkeypatch.setenv("SITE_ID", SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)
    monkeypatch.setattr("apps.core.inventario._sessao", lambda cookie: {"autenticado": True, "id": P})


def guardar(client, acao, **dados):
    url = reverse("inventario")
    revisao = client.get(url, HTTP_COOKIE="meshcraft_sessao=A").json()["revisao"]
    return client.post(url, {"acao": acao, "revisao": revisao, **dados}, HTTP_COOKIE="meshcraft_sessao=A")


def destino_do_cartao(html):
    ancora = re.search(r'<a\b(?=[^>]*\bid="inicio-retomar")[^>]*>', html)
    assert ancora, "A Base deve ter o link de retomada"
    destino = re.search(r'\bhref="([^"]+)"', ancora.group())
    assert destino
    return unescape(destino.group(1))


@pytest.mark.parametrize("ordem,nome", enumerate(ETAPAS, start=1))
def test_cada_etapa_tem_rota_pagina_e_formulario_proprios(client, ordem, nome):
    url = reverse(nome)
    assert url == ("/inicio/motivo/", "/inicio/objetivo/", "/inicio/item/")[ordem - 1]
    r = client.get(url)
    assert r.status_code == 200
    assert r.context["entrou"] is True and r.context["inicio_etapa"] == ordem
    assert r.context["inicio_titulo"]
    assert r.context["faixas"]
    assert "gamificacao/inicio_pagina.html" in [t.name for t in r.templates]
    corpo = r.content.decode()
    assert 'id="inicio-jornada"' in corpo
    assert corpo.count("<form") == 1
    assert "private" in r["Cache-Control"] and "no-store" in r["Cache-Control"]
    assert r["X-Robots-Tag"] == "noindex, nofollow"
    assert ("name=\"sonho\"" in corpo) is (ordem == 2)
    assert ("id=\"inicio-pedir-ajuda\"" in corpo) is (ordem == 3)


def test_visitante_encontra_convite_sem_dados_privados(client, monkeypatch):
    assert guardar(client, "inicio-plano", sonho="SONHO-PRIVADO-ALFA", objetivo="OBJETIVO-PRIVADO-ALFA").status_code == 200
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: None)
    for nome in ("base", *ETAPAS):
        r = client.get(reverse(nome))
        corpo = r.content.decode()
        assert r.status_code == 200 and "Entrar na escola" in corpo
        assert "SONHO-PRIVADO-ALFA" not in corpo and "OBJETIVO-PRIVADO-ALFA" not in corpo
        assert 'id="inicio-jornada"' not in corpo


def test_cartao_retoma_primeiro_passo_pendente_sem_expor_plano(client):
    base = reverse("base")
    corpo = client.get(base).content.decode()
    assert 'id="inicio-cartao"' in corpo
    assert destino_do_cartao(corpo) == reverse("inicio-motivo")

    assert guardar(client, "inicio-motivo", motivo="ugc", motivo_pessoal="MOTIVO-PRIVADO-ALFA").status_code == 200
    assert destino_do_cartao(client.get(base).content.decode()) == reverse("inicio-objetivo")
    assert guardar(client, "inicio-plano", sonho="SONHO-PRIVADO-ALFA", objetivo="OBJETIVO-PRIVADO-ALFA",
                   compromisso="COMPROMISSO-PRIVADO-ALFA", assumir="sim").status_code == 200
    corpo = client.get(base).content.decode()
    assert destino_do_cartao(corpo) == reverse("inicio-item")
    for segredo in ("SONHO-PRIVADO-ALFA", "OBJETIVO-PRIVADO-ALFA", "COMPROMISSO-PRIVADO-ALFA", "MOTIVO-PRIVADO-ALFA"):
        assert segredo not in corpo

    # Concluir a entrega mantém as páginas acessíveis para releitura e edição.
    from django.core.files.uploadedfile import SimpleUploadedFile
    arquivo = SimpleUploadedFile("item.obj", b"v 0 0 0\nv 1 0 0\nv 0 1 0\nf 1 2 3\n")
    assert guardar(client, "anexo", passo="2", arquivo=arquivo).status_code == 200
    assert guardar(client, "declaracao", passo="2", estado="feito").status_code == 200
    corpo = client.get(base).content.decode()
    assert "Revisitar meu começo" in corpo
    assert destino_do_cartao(corpo) == reverse("inicio-motivo")
    assert client.get(reverse("inicio-item")).status_code == 200
    assert guardar(client, "inicio-motivo", motivo="jogo").status_code == 200


def test_paginas_nao_perdem_registro_e_respeitam_pessoa_e_site(client, monkeypatch):
    assert guardar(client, "inicio-motivo", motivo="estudio", motivo_pessoal="Minha razão").status_code == 200
    assert guardar(client, "inicio-plano", sonho="Sonho reservado", objetivo="Minha peça").status_code == 200
    salvo = JornadaPessoal.objects.get(pessoa_id=P, site_id=SITE)
    for nome in ETAPAS:
        assert client.get(reverse(nome)).status_code == 200
    salvo.refresh_from_db()
    assert salvo.inicio["sonho"] == "Sonho reservado" and salvo.inicio["motivo"] == "estudio"
    assert client.get(reverse("inventario"), HTTP_COOKIE="meshcraft_sessao=A").json()["inicio"]["objetivo"] == "Minha peça"

    monkeypatch.setattr("apps.core.views.quem_e", lambda request: "outro-aluno")
    for nome in ("base", *ETAPAS):
        assert "Sonho reservado" not in client.get(reverse(nome)).content.decode()
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: P)
    monkeypatch.setenv("SITE_ID", "outro-site")
    for nome in ("base", *ETAPAS):
        assert "Sonho reservado" not in client.get(reverse(nome)).content.decode()
    assert JornadaPessoal.objects.filter(pessoa_id=P, site_id=SITE).count() == 1


def test_links_entre_paginas_respeitam_prefixo_publico(client):
    prefixo_anterior = get_script_prefix()
    try:
        with override_settings(FORCE_SCRIPT_NAME="/conquistas"):
            set_script_prefix("/conquistas/")
            r = client.get("/inicio/motivo/", SCRIPT_NAME="/conquistas")
            assert r.status_code == 200
            corpo = r.content.decode()
            assert '/conquistas/inicio/objetivo/' in corpo
            assert '/conquistas/inicio/item/' in corpo
            assert '/conquistas/inventario/' in corpo
    finally:
        set_script_prefix(prefixo_anterior)
