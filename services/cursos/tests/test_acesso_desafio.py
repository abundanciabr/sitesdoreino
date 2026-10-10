from datetime import timedelta
from unittest import mock

from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.core import acesso_desafio


def test_enderecos_nao_caem_no_mapa_do_curso():
    assert resolve("/acesso-desafio-como-ganhar-em-dolar-com-roblox/").func is acesso_desafio.acesso
    assert resolve("/evento-desafio-como-ganhar-em-dolar-com-roblox/").func is acesso_desafio.evento


def test_acesso_tem_o_texto_e_leva_ao_evento():
    html = acesso_desafio.acesso(RequestFactory().get("/")).content.decode()
    assert "Informações importantes" in html
    assert "Seja muito bem-vindo à área do participante do Desafio Como Ganhar em Dólar com Roblox!" in html
    assert "19 de outubro, às 9h da manhã" in html
    assert f'href="{reverse("evento-desafio-roblox")}">clique aqui</a>' in html
    for de_fora in ("Fórmula de Lançamento Pago", "ericoeleandroladeira", "tally.so"):
        assert de_fora not in html


def test_evento_conta_ate_a_aula_1_e_depois_libera():
    antes = acesso_desafio.AULA_1 - timedelta(days=2, hours=3, minutes=4, seconds=5)
    with mock.patch("apps.core.acesso_desafio.timezone.now", return_value=antes):
        html = acesso_desafio.evento(RequestFactory().get("/")).content.decode()
    assert 'id="dias">02<' in html and 'id="horas">03<' in html
    assert 'id="minutos">04<' in html and 'id="segundos">05<' in html
    assert 'data-alvo="2026-10-19T09:00:00-03:00"' in html
    assert 'id="liberada" hidden' in html

    depois = acesso_desafio.AULA_1 + timedelta(seconds=1)
    with mock.patch("apps.core.acesso_desafio.timezone.now", return_value=depois):
        html = acesso_desafio.evento(RequestFactory().get("/")).content.decode()
    assert 'id="contagem"' in html and "hidden>" in html.split('id="contagem"')[1].split("\n")[0]
    assert 'id="liberada">' in html


def test_as_duas_paginas_tem_o_botao_de_suporte():
    for view in (acesso_desafio.acesso, acesso_desafio.evento):
        html = view(RequestFactory().get("/")).content.decode()
        assert "cursos/suporte.js" in html and "cursos/suporte.css" in html
        assert 'data-curso="desafio-como-ganhar-em-dolar-com-roblox"' in html
