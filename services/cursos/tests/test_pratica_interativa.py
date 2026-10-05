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
    ],
)
def test_so_pratica_da_casa_e_embutida(url):
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
    assert 'srcdoc="' in html
    assert "Colorindo seu primeiro pet" in html
    assert 'href="/proxima"' in html
