import datetime as dt
import uuid

import pytest
from django.test import Client

from apps.matriculas.models import Matricula

pytestmark = pytest.mark.django_db
URL='/api/alunos/jornada-acesso/medicoes?site_id=escola&de=2026-10-01&ate=2026-10-23'


def linha(**campos):
    data=dt.datetime.fromisoformat('2026-10-02T12:00:00+00:00')
    return Matricula.objects.create(**{ 'site_id':'escola', 'order_id':'pre:'+uuid.uuid4().hex,
        'email':'aluno@example.test', 'name':'Teste', 'status':'ativa', 'decidido_em':data,
        'aviso_event_id':uuid.uuid4(), 'acesso_consumido_em':data+dt.timedelta(hours=1), **campos})


def test_so_conta_uso_real_apos_liberacao_sem_duplicar_pessoa(settings):
    settings.TOKENS_ACEITOS={'par-teste'}
    linha()
    linha(email=' ALUNO@example.test ')
    linha(email='outro@example.test', acesso_consumido_em=None)
    linha(email='sem-link@example.test', aviso_event_id=None, acesso_consumido_em=None)
    linha(email='teste@example.test', em_teste=True)
    linha(email='outro-site@example.test',site_id='outro')
    linha(email='cedo@example.test',acesso_consumido_em=dt.datetime.fromisoformat('2026-10-01T12:00:00+00:00'))
    linha(email='fora@example.test',decidido_em=dt.datetime.fromisoformat('2026-10-01T00:30:00+00:00'))
    r=Client().get(URL,HTTP_AUTHORIZATION='Bearer par-teste')
    assert r.status_code==200
    corpo=r.json()
    assert (corpo['liberadas'],corpo['com_link'],corpo['usaram_link'])==(4,3,1)
    assert 'email' not in str(corpo) and 'aluno@example.test' not in str(corpo)


def test_fonte_vazia_e_zero_real_e_porta_continua_fechada(settings):
    settings.TOKENS_ACEITOS={'par-teste'}
    assert Client().get(URL).status_code==401
    r=Client().get(URL,HTTP_AUTHORIZATION='Bearer par-teste')
    assert r.json()['usaram_link']==0
    assert Client().get(URL.replace('de=2026-10-01','de=2026-11-01'),HTTP_AUTHORIZATION='Bearer par-teste').status_code==422
