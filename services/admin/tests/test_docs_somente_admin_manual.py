import io
import re

import pytest
from django.conf import settings
from django.core import signing
from django.core.management import call_command
from django.db import connection, transaction, DatabaseError
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento


@pytest.fixture(autouse=True)
def ambiente(settings):
    settings.ADMIN_EMAILS = 'admin@exemplo.com'
    Documento.objects.all().delete()


def admin():
    cliente = Client(enforce_csrf_checks=True)
    cliente.cookies[settings.ADMIN_LOCAL_COOKIE_NAME] = signing.TimestampSigner().sign_object(
        {'id': 'admin-teste', 'email': 'admin@exemplo.com', 'nome': 'Admin'})
    return cliente


def publico(cliente, documento):
    pagina = cliente.get('/documentos/' + documento.nome)
    assert pagina.status_code == 200
    intencao = re.search(r'name="intencao_publicar" value="([^"]+)"', pagina.content.decode()).group(1)
    return cliente.post('/documentos/' + documento.nome + '/publicar',
                        {'intencao_publicar': intencao,
                         'csrfmiddlewaretoken': cliente.cookies[settings.CSRF_COOKIE_NAME].value})


def robo():
    saida = io.StringIO()
    call_command('conta_do_robo', 'emitir', stdout=saida, stderr=io.StringIO())
    return Client(enforce_csrf_checks=True, HTTP_AUTHORIZATION='Robo ' + saida.getvalue().strip())


@pytest.mark.parametrize('caminho', [
    '/documentos/criar', '/documentos/alvo/publicar', '/documentos/alvo/salvar',
    '/documentos/alvo/desarquivar', '/documentos/alvo/restaurar',
    '/documentos/alvo/arquivar', '/documentos/alvo/midia/enviar',
])
def test_robo_nao_escreve_nem_publica(caminho):
    doc = Documento.objects.create(nome='alvo', titulo='Alvo', corpo='original')
    assert robo().post(caminho, {'titulo': 'invasor', 'corpo': 'mudou'}).status_code == 403
    doc.refresh_from_db()
    assert doc.corpo == 'original' and not doc.no_ar
    assert Documento.objects.count() == 1


def test_admin_precisa_do_formulario_e_csrf():
    doc = Documento.objects.create(nome='alvo', titulo='Alvo')
    cliente = admin()
    assert cliente.post('/documentos/alvo/publicar').status_code == 403
    cliente.get('/documentos/alvo')
    assert cliente.post('/documentos/alvo/publicar',
                        {'csrfmiddlewaretoken': cliente.cookies[settings.CSRF_COOKIE_NAME].value}).status_code == 403
    assert publico(cliente, doc).status_code == 302
    doc.refresh_from_db()
    assert doc.no_ar
    assert Client().get('/docs/alvo').status_code == 200
    assert '/docs/alvo' in Client().get('/docs/').content.decode()


def test_intencao_de_outra_sessao_nao_publica():
    doc = Documento.objects.create(nome='alvo', titulo='Alvo')
    primeiro = admin()
    pagina = primeiro.get('/documentos/alvo')
    intencao = re.search(r'name="intencao_publicar" value="([^"]+)"', pagina.content.decode()).group(1)
    segundo = admin()
    segundo.get('/documentos/alvo')
    assert segundo.post('/documentos/alvo/publicar', {
        'intencao_publicar': intencao,
        'csrfmiddlewaretoken': segundo.cookies[settings.CSRF_COOKIE_NAME].value}).status_code == 403


def test_formulario_antigo_nao_publica_texto_alterado():
    doc = Documento.objects.create(nome='alvo', titulo='Alvo')
    cliente = admin()
    pagina = cliente.get('/documentos/alvo')
    intencao = re.search(r'name="intencao_publicar" value="([^"]+)"', pagina.content.decode()).group(1)
    Documento.objects.filter(pk=doc.pk).update(corpo='mudou depois de abrir')
    assert cliente.post('/documentos/alvo/publicar', {
        'intencao_publicar': intencao,
        'csrfmiddlewaretoken': cliente.cookies[settings.CSRF_COOKIE_NAME].value}).status_code == 403


@pytest.mark.parametrize('operacao', ['criar', 'atualizar', 'sql'])
def test_banco_recusa_publicacao_direta(operacao):
    assert connection.vendor == 'postgresql'
    doc = Documento.objects.create(nome='alvo', titulo='Alvo')
    with pytest.raises(DatabaseError), transaction.atomic():
        if operacao == 'criar':
            Documento.objects.create(nome='intruso', titulo='Intruso', publico=True)
        elif operacao == 'atualizar':
            Documento.objects.filter(pk=doc.pk).update(publico=True)
        else:
            tabela = connection.ops.quote_name(Documento._meta.db_table)
            with connection.cursor() as cursor:
                cursor.execute(f'UPDATE {tabela} SET publico = true WHERE id = %s', [doc.pk])
    assert Client().get('/docs/alvo').status_code == 404


def test_banco_recusa_reescrever_pagina_publicada():
    doc = Documento.objects.create(nome='alvo', titulo='Alvo')
    assert publico(admin(), doc).status_code == 302
    with pytest.raises(DatabaseError), transaction.atomic():
        Documento.objects.filter(pk=doc.pk).update(corpo='invasor')
    assert 'invasor' not in Client().get('/docs/alvo').content.decode()


def test_assinatura_fabricada_nao_abre_pagina_ou_moldura():
    doc = Documento.objects.create(nome='alvo', titulo='Alvo', formato='pagina')
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('meshcraft.docs_manual', 'fabricada', true)")
        Documento.objects.filter(pk=doc.pk).update(publico=True, publicacao_manual='fabricada')
        with connection.cursor() as cursor:
            cursor.execute("SELECT set_config('meshcraft.docs_manual', '', true)")
    doc.refresh_from_db()
    assert not doc.no_ar
    assert Client().get('/docs/alvo').status_code == 404
    assert Client().get('/docs/alvo/moldura').status_code == 404
    assert '/docs/alvo' not in Client().get('/docs/').content.decode()


@pytest.mark.parametrize('gesto', ['salvar', 'arquivar', 'restaurar'])
def test_editar_arquivar_e_restaurar_nao_republicam(gesto):
    doc = Documento.objects.create(nome='alvo', titulo='Alvo', corpo='original')
    cliente = admin()
    assert publico(cliente, doc).status_code == 302
    dados = {'titulo': 'Alvo', 'corpo': 'editado',
             'csrfmiddlewaretoken': cliente.cookies[settings.CSRF_COOKIE_NAME].value}
    if gesto == 'restaurar':
        dados['versao'] = doc.versoes.first().pk
    assert cliente.post('/documentos/alvo/' + gesto, dados).status_code == 302
    if gesto == 'arquivar':
        assert cliente.post('/documentos/alvo/desarquivar', dados).status_code == 302
    doc.refresh_from_db()
    assert not doc.no_ar and not doc.publicacao_manual
    assert Client().get('/docs/alvo').status_code == 404


def test_semear_nunca_publica(tmp_path, monkeypatch):
    (tmp_path / 'semente.md').write_text('---\ntitulo: Semente\npublico: true\n---\nTexto')
    monkeypatch.setattr(documentos, 'CANDIDATOS', [tmp_path])
    assert documentos.semear_documento(Documento, 'semente')
    assert not Documento.objects.get(nome='semente').no_ar
    assert Client().get('/docs/semente').status_code == 404


def test_comunidade_retirada_nao_tem_excecao_no_prefixo_docs():
    Documento.objects.create(nome='comunidade', titulo='Comunidade', formato='pagina')
    for cliente in [Client(), admin(), robo()]:
        assert cliente.get('/docs/comunidade').status_code == 404
        assert cliente.get('/docs/comunidade/moldura').status_code == 404


def test_anonimo_nao_cria():
    assert Client().post('/documentos/criar', {'titulo': 'intruso'}).status_code in (302, 403)
    assert not Documento.objects.exists()
