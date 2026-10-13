"""O cadastro volta ao mesmo site do curso sem mudar os direitos existentes."""
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection
from apps.matriculas.models import Matricula

migracao = import_module('apps.matriculas.migrations.0010_identificador_meshcraft_legado')
pytestmark = pytest.mark.django_db


def executar():
    migracao.corrigir_identificador(apps, SimpleNamespace(connection=connection))


def criar(numero, site='Meshcraft', status='ativa', **campos):
    produto = campos.pop('product_id', 'curso-' + str(numero))
    email = campos.pop('email', 'aluna@example.test')
    return Matricula.objects.create(site_id=site, order_id='cadastro-legado-' + str(numero),
        product_id=produto, email=email, name='Aluna de teste',
        status=status, **campos)


def test_corrige_a_escola_preservando_todos_os_demais_campos():
    for i, status in enumerate(('ativa', 'ativa', 'ativa', 'suspensa', 'reembolsada', 'encerrada')):
        criar(i, status=status, product_id=migracao.PRODUTO_DA_PESQUISA if i == 0 else 'curso-' + str(i), em_teste=True, turma='Turma histórica',
            decidido_por='mantenedor-de-teste', motivo_recusa='Registro histórico')
    antes = list(Matricula.objects.order_by('id').values())
    executar()
    depois = list(Matricula.objects.order_by('id').values())
    esperado = [{**linha, 'site_id': migracao.SITE_CANONICO} if linha['status'] == 'ativa' else linha for linha in antes]
    assert depois == esperado


def test_outros_sites_e_matriculas_ja_corretas_ficam_iguais():
    criar(1, site='outra-escola')
    criar(2, site=migracao.SITE_CANONICO)
    criar(3, site='Meshcraft de outra escola')
    antes = list(Matricula.objects.order_by('id').values())
    executar()
    assert list(Matricula.objects.order_by('id').values()) == antes


def test_repetir_nao_cria_nem_altera_matriculas():
    criar(1, product_id=migracao.PRODUTO_DA_PESQUISA)
    executar()
    antes = list(Matricula.objects.order_by('id').values())
    executar()
    assert list(Matricula.objects.order_by('id').values()) == antes


@pytest.mark.parametrize('campo', ['provider', 'provider_reference_id'])
def test_vinculo_financeiro_impede_toda_a_correcao(campo):
    criar(1, product_id=migracao.PRODUTO_DA_PESQUISA)
    criar(2, **{campo: 'referencia-de-teste'})
    antes = list(Matricula.objects.order_by('id').values())
    with pytest.raises(RuntimeError, match='não aplicada'):
        executar()
    assert list(Matricula.objects.order_by('id').values()) == antes


def test_outra_conta_legada_sem_esse_vinculo_fica_igual():
    criar(1, product_id=migracao.PRODUTO_DA_PESQUISA)
    outra = criar(2, email='outra@example.test')
    antes = Matricula.objects.values().get(pk=outra.pk)
    executar()
    assert Matricula.objects.values().get(pk=outra.pk) == antes


def test_duas_contas_no_desafio_impedem_alteracao():
    criar(1, product_id=migracao.PRODUTO_DA_PESQUISA)
    criar(2, email='outra@example.test', product_id=migracao.PRODUTO_DA_PESQUISA)
    antes = list(Matricula.objects.order_by('id').values())
    with pytest.raises(RuntimeError, match='ambíguo'):
        executar()
    assert list(Matricula.objects.order_by('id').values()) == antes
