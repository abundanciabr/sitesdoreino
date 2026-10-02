"""Confere que a tela servida não mostra marcas de template."""


def test_a_pagina_renderizada_nao_contem_marca_de_comentario():
    from django.template.loader import render_to_string

    html = render_to_string(
        "admin/visao_geral.html",
        {"admin": {"nome": "Fulano", "email": "f@exemplo.com", "id": "x"}},
    )
    assert "{#" not in html
    assert "#}" not in html
    assert "{%" not in html
