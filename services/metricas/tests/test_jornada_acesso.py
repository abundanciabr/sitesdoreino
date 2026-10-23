import datetime as dt
import uuid

import pytest
from django.test import Client

from apps.fatos.models import Evento, dia_em_sao_paulo

pytestmark = pytest.mark.django_db
URL = '/api/metricas/jornada-acesso?site_id=escola&de=2026-10-01&ate=2026-10-23'


def fato(tipo, dados, ator='', quando='2026-10-02T12:00:00+00:00', site='escola'):
    data = dt.datetime.fromisoformat(quando)
    return Evento.objects.create(event_id=uuid.uuid4(), tipo=tipo, versao=1, site_id=site,
        ocorrido_em=data, dia=dia_em_sao_paulo(data), dados=dados, ator_id=ator)


def ler(settings):
    settings.TOKENS_ACEITOS = {'par-teste'}
    r = Client().get(URL, HTTP_AUTHORIZATION='Bearer par-teste')
    assert r.status_code == 200
    return {l['chave']: l for l in r.json()['leituras']}


def test_distingue_pessoa_matricula_autor_e_fecha_site_e_janela(settings):
    for _ in range(2):
        fato('identidade.pessoa-cadastrada', {'pessoa_id': 'p1'})
        fato('matricula.situacao-alterada', {'matricula_id': 'm1', 'situacao_nova': 'aguardando'})
    fato('identidade.pessoa-cadastrada', {'pessoa_id': 'outra'}, site='outro')
    fato('identidade.pessoa-cadastrada', {'pessoa_id': 'fora'}, quando='2026-10-01T00:30:00+00:00')
    fato('matricula.situacao-alterada', {'matricula_id': 'm1', 'situacao_nova': 'ativa', 'origem': 'liberado'})
    fato('matricula.situacao-alterada', {'matricula_id': 'm2', 'situacao_nova': 'ativa', 'origem': 'comprou'})
    fato('forum.topico-criado', {}, ator='autor1')
    fato('forum.mensagem-criada', {}, ator='autor1')
    fato('forum.mensagem-criada', {}, ator='autor2')
    fato('forum.topico-criado', {}, ator='')
    linhas = ler(settings)
    assert {k: l['quantidade'] for k,l in linhas.items()} == {'cadastros':1,'pedidos':1,'liberacoes':1,'forum':2}
    assert linhas['forum']['sem_identificador'] == 1
    assert 'autor1' not in str(linhas)


def test_sem_fato_e_diferente_de_zero_no_periodo(settings):
    assert ler(settings)['cadastros']['quantidade'] is None
    fato('identidade.pessoa-cadastrada', {'pessoa_id':'p'}, quando='2026-09-02T12:00:00+00:00')
    assert ler(settings)['cadastros']['quantidade'] == 0


def test_nao_abre_sem_cracha_e_recusa_intervalo_invertido(settings):
    settings.TOKENS_ACEITOS = {'par-teste'}
    assert Client().get(URL).status_code == 401
    assert Client().get(URL.replace('de=2026-10-01','de=2026-11-01'), HTTP_AUTHORIZATION='Bearer par-teste').status_code == 422
