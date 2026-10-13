from types import SimpleNamespace

import pytest
from django.template import Context, Template
from django.test import RequestFactory
from apps.core.sessao import Ator, VISITANTE


@pytest.mark.parametrize("ator,visivel", [
    (VISITANTE, False),
    (Ator(pessoa=SimpleNamespace(), eh_aluno=True), False),
    (Ator(pessoa=SimpleNamespace(), eh_professor=True), False),
    (Ator(pessoa=None, eh_admin=True), False),
    (Ator(pessoa=SimpleNamespace(), eh_admin=True), True),
])
def test_bloco_admin_usa_autorizacao_da_requisicao(ator, visivel):
    request = RequestFactory().get("/")
    request._ator_desta_requisicao = ator
    template = Template('{% load botoes_admin %}{% somente_admin %}<button>Reservado</button>{% endsomente_admin %}')
    resultado = template.render(Context({"request": request, "previa_admin": True}))
    assert ("Reservado" in resultado) is visivel


def test_bloco_sem_requisicao_nao_mostra_botao():
    template = Template('{% load botoes_admin %}{% somente_admin %}Reservado{% endsomente_admin %}')
    assert template.render(Context({"previa_admin": True})) == ""
