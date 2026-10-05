import json
import uuid
import pytest
from apps.core.models import Lead, TimelineEvent, Oportunidade
from apps.core.pessoas_reais import ContatoDeTeste
from apps.core.handlers import ao_quiz_completado, processar_envelope, ao_pedido_criado
from apps.core.quiz_do_lead import ao_quiz_captura_parcial
from apps.core.alunos import sincronizar_matricula
from apps.core.cadastros_crm import incluir

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def bloqueio(settings, permitir_fixtures_no_banco_isolado):
    settings.CRM_REJEITAR_TESTES = True


@pytest.mark.parametrize('dados', [
    {'email':'ana@example.com'}, {'name':'Aluno Teste'},
    {'source':'sandbox'}, {'email':'pessoa@teste.meshcraft.top'},
    {'tags':['teste']}, {'site_id':'canario-fase-3'},
])
def test_modelo_bloqueia_criacao_e_lotes(dados):
    campos={'site_id':'site-a','email':'ana@dominio.com',**dados}
    with pytest.raises(ContatoDeTeste): Lead.objects.create(**campos)
    with pytest.raises(ContatoDeTeste): Lead.objects.bulk_create([Lead(**campos)])
    assert Lead.objects.count()==0


def test_atualizacao_nao_converte_pessoa_real_em_teste():
    lead=Lead.objects.create(site_id='s',email='ana@dominio.com',name='Ana')
    with pytest.raises(ContatoDeTeste): Lead.objects.filter(pk=lead.pk).update(name='Teste')
    lead.name='Teste'
    with pytest.raises(ContatoDeTeste): lead.save()
    lead.refresh_from_db()
    assert lead.name=='Ana'


def test_api_recusa_teste_e_aceita_pessoa_real(client,settings):
    settings.TOKENS_ACEITOS={'token'}
    def enviar(dados):
        return client.post('/api/leads/leads',data=json.dumps(dados),content_type='application/json',HTTP_AUTHORIZATION='Bearer token')
    assert enviar({'site_id':'s','email':'a@example.com'}).status_code==422
    assert enviar({'site_id':'s','email':'ana@dominio.com','name':'Ana'}).status_code==200
    assert Lead.objects.count()==1


@pytest.mark.parametrize('handler', [ao_quiz_completado,ao_quiz_captura_parcial,ao_pedido_criado])
def test_evento_de_teste_consumido_sem_contato_ou_oportunidade(handler):
    envelope={'event_id':str(uuid.uuid4()),'data':{'site_id':'s','em_teste':True,'customer':{'email':'ana@dominio.com'}}}
    assert processar_envelope(envelope,handler)
    assert not processar_envelope(envelope,handler)
    assert Lead.objects.count()==TimelineEvent.objects.count()==Oportunidade.objects.count()==0


def test_sincronizacao_nao_reintroduz_testes():
    assert sincronizar_matricula({'id':'m','site_id':'s','email':'a@example.com','status':'ativa'})['ignorada']
    with pytest.raises(ContatoDeTeste):
        incluir(site_id='s',email='a@example.com',dados={'id':'i'})
    assert Lead.objects.count()==0
