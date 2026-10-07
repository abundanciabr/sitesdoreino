import copy
import json
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from apps.core import dia1
from apps.cursos.models import Progresso, Pessoa
from tests.conftest import COOKIE, BETO, dublar_sessao, dublar_matricula

pytestmark = pytest.mark.django_db


@pytest.fixture
def aula1(aluna, esqueleto):
    esqueleto.slug = dia1.CURSO
    esqueleto.progressao = 'livre'
    esqueleto.save()
    a = esqueleto.aulas.get(numero='E00')
    a.numero = 'PET'
    a.estado = 'publicada'
    a.save()
    return a


def url(a, route):
    return reverse(route, args=[a.curso.slug, a.bloco.parte, a.numero])


def gravar(client, a, e, revisao=0, concluir=False):
    return client.post(url(a, 'dia1-salvar'), json.dumps({'estado': e, 'revisao': revisao, 'concluir': concluir}), content_type='application/json', HTTP_COOKIE=COOKIE)


def completa():
    e = dia1.inicial()
    e.update(etapa=11, copiado=True, traduzido=True, resposta='Olá, Alex!', ingles='Hello, Alex!', enviado=True, promessa=True)
    e['objeto'] = {'altura': 1.8, 'ponta': .08, 'x': -1, 'y': 1.1}
    e['acoes'] = ['girar', 'esticar', 'afinar', 'mover', 'olhar']
    return e


def test_retomada_conserva_quiz_sem_concluir_por_video(aula1, client):
    page = client.get(url(aula1, 'aula-do-curso'), HTTP_COOKIE=COOKIE)
    assert page.status_code == 200 and b'dia1-config' in page.content
    p = Progresso.objects.get(aula=aula1)
    p.autoavaliacao = {'respostas': ['Registro anterior']}
    p.save()
    e = completa(); e['etapa'] = 8; e['promessa'] = False; e['video'] = 418
    assert gravar(client, aula1, e).status_code == 200
    p.refresh_from_db()
    assert p.autoavaliacao['respostas'] == ['Registro anterior']
    assert not p.concluida_em
    assert dia1.estado(p)['objeto']['x'] == -1
    assert client.get(url(aula1, 'aula-do-curso'), HTTP_COOKIE=COOKIE).status_code == 200
    assert gravar(client, aula1, e, 0).status_code == 409
    assert gravar(client, aula1, e, 1, True).status_code == 422
    assert client.post(url(aula1, 'concluir-aula-do-curso'), HTTP_COOKIE=COOKIE).status_code == 302
    p.refresh_from_db(); assert not p.concluida_em


def test_conclusao_pelo_pedido_modelo_e_promessa(aula1, client):
    assert gravar(client, aula1, completa(), concluir=True).status_code == 200
    p = Progresso.objects.get(aula=aula1)
    assert p.concluida_em and p.estado == 'concluida'
    assert gravar(client, aula1, completa(), 1, True).status_code == 200


def test_alunos_separados_e_mural_sem_conversa(aula1, client, rede):
    e = completa(); e['mural'] = True; e['resposta'] = 'Minha conversa privada'
    assert gravar(client, aula1, e).status_code == 200
    dublar_sessao(rede, BETO); dublar_matricula(rede, BETO['email'])
    page = client.get(url(aula1, 'aula-do-curso'), HTTP_COOKIE=COOKIE)
    assert page.status_code == 200 and b'Minha conversa privada' not in page.content
    assert gravar(client, aula1, dia1.inicial()).status_code == 200
    assert Progresso.objects.filter(aula=aula1, autoavaliacao__dia1_alex_v1__enviado=True).count() == 1
    dublar_sessao(rede, {'autenticado': False})
    assert client.post(url(aula1, 'dia1-salvar'), '{}', content_type='application/json').status_code == 403


def test_traducao_do_texto_editado_e_falha_recuperavel(aula1, client):
    u = url(aula1, 'dia1-tradutor')
    with patch.object(dia1, '_traduzir', return_value='Hello, Alex!') as traducao:
        r = client.post(u, json.dumps({'texto': 'Oi, Alex!', 'direcao': 'en'}), content_type='application/json', HTTP_COOKIE=COOKIE)
        assert r.json()['texto'] == 'Hello, Alex!'
        traducao.assert_called_once_with('Oi, Alex!')
    with patch.object(dia1, '_traduzir', return_value=None):
        assert client.post(u, json.dumps({'texto': 'Texto livre', 'direcao': 'en'}), content_type='application/json', HTTP_COOKIE=COOKIE).status_code == 503
    assert Client(enforce_csrf_checks=True).post(u, '{}', content_type='application/json', HTTP_COOKIE=COOKIE).status_code == 403


def test_nao_destroi_acesso_antigo_e_recusa_objeto_invalido(aula1, client):
    assert gravar(client, aula1, completa(), concluir=True).status_code == 200
    assert gravar(client, aula1, dia1.inicial(), 1).status_code == 200
    p = Progresso.objects.get(aula=aula1); assert p.concluida_em
    e = dia1.inicial(); e['objeto']['altura'] = float('nan')
    assert gravar(client, aula1, e, 2).status_code == 400
    p.refresh_from_db(); assert dia1.estado(p)['revisao'] == 2
