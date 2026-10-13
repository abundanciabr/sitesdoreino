import re
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.conf import settings
from django.core import signing
from django.db import close_old_connections, connection
from django.test import Client

from apps.core.models import Documento, VersaoDoDocumento

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.ADMIN_EMAILS = 'editor-teste@exemplo.invalid'


def abrir(nome):
    cliente = Client(enforce_csrf_checks=True)
    cliente.cookies[settings.ADMIN_LOCAL_COOKIE_NAME] = signing.TimestampSigner().sign_object(
        {'id': 'editor-isolado', 'email': 'editor-teste@exemplo.invalid', 'nome': 'Teste'})
    pagina = cliente.get('/documentos/' + nome + '/editar')
    assert pagina.status_code == 200
    base = re.search(r'name="versao_base" value="([^"]+)"', pagina.content.decode()).group(1)
    return cliente, base


def salvar(cliente, nome, base, texto):
    return cliente.post('/documentos/' + nome + '/salvar', {
        'titulo': 'Teste', 'corpo': texto, 'versao_base': base,
        'csrfmiddlewaretoken': cliente.cookies[settings.CSRF_COOKIE_NAME].value})


def test_formulario_antigo_preserva_texto_e_historico():
    doc = Documento.objects.create(nome='conflito-teste', titulo='Teste', corpo='BASE')
    a, base_a = abrir(doc.nome)
    b, base_b = abrir(doc.nome)
    assert base_a == base_b
    assert salvar(b, doc.nome, base_b, 'B').status_code == 302
    resposta = salvar(a, doc.nome, base_a, 'A preservado')
    assert resposta.status_code == 409
    assert 'A preservado' in resposta.content.decode()
    doc.refresh_from_db()
    assert doc.corpo == 'B'
    assert list(doc.versoes.values_list('corpo', flat=True)) == ['B']
    assert not doc.publico and not doc.publicacao_manual
    atual, base_atual = abrir(doc.nome)
    assert salvar(atual, doc.nome, base_atual, 'B + A').status_code == 302
    doc.refresh_from_db()
    assert doc.corpo == 'B + A' and doc.versoes.count() == 2


@pytest.mark.parametrize('base', ['', 'invalida', '-1'])
def test_versao_ausente_ou_invalida_nao_grava(base):
    doc = Documento.objects.create(nome='base-teste', titulo='Teste', corpo='BASE')
    cliente, _ = abrir(doc.nome)
    assert salvar(cliente, doc.nome, base, 'nao gravar').status_code == 409
    doc.refresh_from_db()
    assert doc.corpo == 'BASE' and not doc.versoes.exists()


def provar_duas_gravacoes_simultaneas_tem_um_vencedor():
    assert connection.vendor == 'postgresql', 'Ensaio exige PostgreSQL isolado'
    doc = Documento.objects.create(nome='simultaneo-teste', titulo='Teste', corpo='BASE')
    clientes = [abrir(doc.nome), abrir(doc.nome)]
    barreira = Barrier(2)

    def executar(i):
        close_old_connections()
        try:
            cliente, base = clientes[i]
            barreira.wait(timeout=10)
            return salvar(cliente, doc.nome, base, 'EDITOR ' + str(i)).status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as pool:
        respostas = list(pool.map(executar, range(2)))
    assert sorted(respostas) == [302, 409]
    doc.refresh_from_db()
    assert doc.corpo in ('EDITOR 0', 'EDITOR 1')
    assert VersaoDoDocumento.objects.filter(documento=doc).count() == 1
    assert not doc.publico and not doc.publicacao_manual
