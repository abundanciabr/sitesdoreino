from types import SimpleNamespace

import pytest
from django.http import Http404

from apps.quiz.experiencias import calcular, resolver_experiencia


def versao(**experience):
    return SimpleNamespace(experience=experience)


def test_formato_segmento_e_alias():
    version = versao(
        default_format="text",
        formats={
            "text": {"headline": "Geral", "subheadline": "Base"},
            "ai": {"headline": "IA", "subheadline": "Aviso"},
        },
        segments={
            "novo": {
                "headline": "Novo",
                "results": {"alto": {"title": "Alto"}},
                "ignored": "x",
            }
        },
    )
    resolved = resolver_experiencia(version, seg="novo")
    assert resolved["headline"] == "Novo"
    assert resolved["subheadline"] == "Base"
    assert resolved["results"]["alto"]["title"] == "Alto"
    assert "ignored" not in resolved
    assert resolver_experiencia(version, fmt="ai_agent")["fmt"] == "ai"
    assert resolver_experiencia(version, fmt="ai")["ai_disponivel"] is False
    with pytest.raises(Http404):
        resolver_experiencia(version, fmt="calc")
    with pytest.raises(Http404):
        resolver_experiencia(version, seg="desconhecido")


@pytest.mark.parametrize(
    "url,kind",
    [
        ("https://cdn.example.com/a.mp4", "file"),
        ("https://cdn.example.com/a.webm?token=abc", "file"),
        ("https://www.youtube-nocookie.com/embed/abcdefghijk", "embed"),
    ],
)
def test_video_permitido(url, kind):
    version = versao(formats={"video": {"video_url": url}})
    assert resolver_experiencia(version, "video")["video_kind"] == kind


def test_segmento_com_video_nulo_preserva_video_do_formato():
    url = "https://cdn.example.com/base.mp4"
    version = versao(
        formats={"video": {"headline": "Vídeo", "video_url": url}},
        segments={"novo": {"headline": "Novo", "video_url": None}},
    )
    resolved = resolver_experiencia(version, "video", "novo")
    assert resolved["headline"] == "Novo"
    assert resolved["video_url"] == url
    assert resolved["video_kind"] == "file"


def test_texto_puro_nao_exibe_video_do_segmento():
    version = versao(
        formats={"text": {"headline": "Texto"}},
        segments={
            "novo": {
                "headline": "Novo",
                "video_url": "https://cdn.example.com/video.mp4",
            }
        },
    )
    resolved = resolver_experiencia(version, "text", "novo")
    assert resolved["video_url"] == ""
    assert resolved["video_kind"] == ""


@pytest.mark.parametrize(
    "url",
    [
        "http://cdn.example.com/a.mp4",
        "https://evil.example.com/embed/abcdefghijk",
        "https://www.youtube.com/watch?v=abcdefghijk",
        "https://www.youtube.com/embed/abcdefghijk?autoplay=1",
        "https://cdn.example.com/a.svg",
        "javascript:alert(1)",
    ],
)
def test_video_bloqueado(url):
    with pytest.raises(Http404):
        resolver_experiencia(versao(formats={"video": {"video_url": url}}), "video")


def test_calculadora_com_defaults_e_limites():
    config = {
        "inputs": [
            {"key": "preco", "label": "Preço", "default": 10, "min": 0, "max": 100},
            {"key": "quantidade", "label": "Quantidade", "default": 2, "min": 1},
        ],
        "expression": "preco * quantidade - 3",
        "result_label": "Total estimado",
    }
    assert calcular(config, {}) == {"result": 17.0, "result_label": "Total estimado"}
    with pytest.raises(ValueError):
        calcular(config, {"preco": 101})
    with pytest.raises(ValueError):
        calcular(config, {"preco": "NaN"})


@pytest.mark.parametrize(
    "expression",
    ["__import__('os').system('id')", "x ** 2", "x[0]", "x / 0", "(1e308 * 1e308)"],
)
def test_calculadora_rejeita_expressao_perigosa_ou_invalida(expression):
    config = {"inputs": [{"key": "x", "default": 2}], "expression": expression}
    with pytest.raises(ValueError):
        calcular(config, {})


@pytest.mark.parametrize("fmt", ["video", "hybrid"])
@pytest.mark.parametrize("url", [None, ""])
def test_video_ainda_em_producao_abre_com_aviso(fmt, url):
    resolved = resolver_experiencia(versao(formats={fmt: {"video_url": url}}), fmt)
    assert resolved["fmt"] == fmt
    assert resolved["video_kind"] == "pendente" and resolved["video_url"] == ""
