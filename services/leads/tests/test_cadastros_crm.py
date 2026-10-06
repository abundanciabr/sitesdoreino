import pytest
from apps.core.cadastros_crm import incluir
from apps.core.models import Lead, Oportunidade, TimelineEvent
from apps.core.contatos import contatos_do_crm
pytestmark = pytest.mark.django_db

def test_cadastro_e_matriculas_reutilizam_pessoa_sem_alterar_origem_ou_venda():
    lead = Lead.objects.create(site_id='s',email=' Nome@dominio.com ',source='quiz:primeiro',consent={'whatsapp':False})
    for _ in range(2):
        incluir(site_id='s',email='nome@DOMINIO.com',nome='Pessoa',dados={'id':'pessoa-1'})
        for mid in ('m1','m2'):
            incluir(site_id='s',email='nome@dominio.com',origem='escola',evento='aluno.matricula',dados={'id':mid,'status':'ativa'})
    lead.refresh_from_db()
    assert Lead.objects.count() == Oportunidade.objects.count() == 1
    assert TimelineEvent.objects.count() == 3
    assert lead.source == 'quiz:primeiro'
    assert lead.consent == {'whatsapp':False}
    assert lead.tags == ['aluno']
    assert contatos_do_crm().get() == lead
    assert Oportunidade.objects.get().etapa == 'nova'
    assert Oportunidade.objects.get().compras.count() == 0

def test_cadastro_sem_matricula_e_pedido_pendente_nao_viram_aluno():
    incluir(site_id='s',email='a@dominio.com',dados={'id':'p1'})
    incluir(site_id='s',email='a@dominio.com',evento='aluno.matricula',dados={'id':'m1','status':'aguardando'})
    assert Lead.objects.get().tags == []
    assert Lead.objects.get().source == ''
    assert contatos_do_crm().count() == 1


def test_matricula_sozinha_nao_abre_venda_e_cadastro_posterior_preserva_interesse():
    dados = {'id': 'm1', 'status': 'ativa'}
    for _ in range(2):
        resultado = incluir(site_id='s', email='aluna@dominio.com', origem='escola',
                           evento='aluno.matricula', dados=dados)
        assert resultado['oportunidade_criada'] is False
    lead = Lead.objects.get()
    assert lead.tags == ['aluno']
    assert lead.timeline.filter(event='aluno.matricula').count() == 1
    assert contatos_do_crm().get() == lead
    assert Oportunidade.objects.count() == 0

    resultado = incluir(site_id='s', email='aluna@dominio.com',
                       dados={'id': 'cadastro-interessada'})
    assert resultado['oportunidade_criada'] is True
    assert Oportunidade.objects.get().lead == lead
    assert lead.timeline.count() == 2
