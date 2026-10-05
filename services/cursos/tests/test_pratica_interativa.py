import pytest
from django.template.loader import render_to_string
from types import SimpleNamespace
from apps.core.views import _video_por_url
from apps.cursos.models import Aula


def test_numero_visivel_acompanha_ordem_sem_mudar_identidade():
    aula = Aula(numero="01", ordem=1, titulo_exibido="Aula 1")
    assert aula.titulo_na_ordem == "Aula 2"
    aula.ordem = 3
    assert aula.titulo_na_ordem == "Aula 4"
    assert aula.numero == "01"
    aula.titulo_exibido = "Aula 1 — Colorindo o pet"
    assert aula.titulo_na_ordem == "Aula 4 — Colorindo o pet"
    aula.titulo_exibido = "Modelagem básica"
    assert aula.titulo_na_ordem == "Modelagem básica"


@pytest.mark.parametrize(
    "url",
    [
        "https://outro.example/cursos/static/pet-aula/index.html",
        "http://meshcraft.top/cursos/static/pet-aula/index.html",
        "https://meshcraft.top/cursos/static/outra.html",
        "https://outro.example/cursos/static/joguinho-ep1/index.html",
        "http://meshcraft.top/cursos/static/joguinho-ep1/index.html",
    ],
)
def test_so_pratica_da_casa_e_nativa(url):
    assert not _video_por_url(url)["interativa"]


def test_pratica_aparece_dentro_da_aula_com_navegacao():
    curso = SimpleNamespace(slug="roblox", nome="Roblox")
    aula = SimpleNamespace(
        titulo_na_ordem="Aula 1 — Colorindo o pet",
        numero="PET",
        curso=curso,
        bloco=SimpleNamespace(parte=1),
    )
    video = _video_por_url("https://meshcraft.top/cursos/static/pet-aula/index.html")
    html = render_to_string(
        "cursos/aula.html",
        {
            "aula": aula,
            "curso": curso,
            "video": video,
            "navegacao": {"proxima": {"url": "/proxima", "titulo": "Aula 2"}},
        },
    )
    assert 'id="pratica-interativa"' in html
    assert 'srcdoc=' not in html
    assert '<iframe' not in html
    assert 'data-pratica="screen"' in html
    assert "caozinho-aula-1366x768.mp4" in html
    assert 'href="/proxima"' in html


def test_episodio_usa_a_mesma_integracao_protegida_e_titulo_proprio():
    video = _video_por_url("https://meshcraft.top/cursos/static/joguinho-ep1/index.html")
    assert video["interativa"]
    assert video["pratica_titulo"] == "É só um joguinho?"
    aula = SimpleNamespace(titulo_na_ordem="É só um joguinho?",numero="J01",curso=SimpleNamespace(slug="roblox"),bloco=SimpleNamespace(parte=1))
    html = render_to_string("cursos/aula.html", {"aula":aula,"video":video,"conclusao":{"feita":False},"navegacao":{"anterior":{"url":"/pet","titulo":"Pet"},"proxima":{"url":"/proxima","titulo":"Próxima"}}})
    assert '<iframe' not in html
    assert 'srcdoc=' not in html
    assert 'postMessage' not in html
    assert 'arvore-estudo.blend' in html
    assert 'episodio-1366x768.mp4' in html
    assert 'Concluir esta aula' in html
    assert "Prática guiada: É só um joguinho?" in html
    assert 'href="/proxima"' in html


def test_pratica_nao_carrega_pagina_html_de_apoio(monkeypatch):
    from pathlib import Path
    def recusar_leitura(*args, **kwargs):
        raise AssertionError("A aula não deve ler a página separada")
    monkeypatch.setattr(Path, "read_text", recusar_leitura)
    for pasta in ["pet-aula", "joguinho-ep1"]:
        assert _video_por_url(f"https://meshcraft.top/cursos/static/{pasta}/index.html")["pratica_template"]
