import uuid
from types import SimpleNamespace
from importlib import import_module
import pytest
from django.apps import apps
from django.db import connection
from apps.core.models import Lead, ContatoDeAcesso, TimelineEvent
from apps.core.acesso_alunos import resolver, Consulta

@pytest.fixture(scope="session")
def django_db_modify_db_settings():
    from django.conf import settings
    settings.DATABASES["default"]["OPTIONS"].pop("pool",None)

@pytest.fixture
def req(monkeypatch,db):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN","admin-test")
    return SimpleNamespace(auth="admin-test")

def consulta(req,canal="whatsapp",contato="+55 96 98408-6018",site="s1"):
    return resolver(req,Consulta(site_id=site,canal=canal,contato=contato))

def test_normaliza_e_isola_site(req):
    ContatoDeAcesso.objects.create(id=uuid.uuid4(),site_id="s1",email="a@escola.test",telefone="5596984086018")
    assert consulta(req)["email"]=="a@escola.test"
    assert consulta(req,contato="96 98408-6018")["email"]=="a@escola.test"
    assert consulta(req,site="s2")=={"encontrado":False}

def test_telefone_compartilhado_nao_escolhe_uma_conta(req):
    for email in ("a@escola.test","b@escola.test"):
        ContatoDeAcesso.objects.create(id=uuid.uuid4(),site_id="s1",email=email,telefone="5596984086018")
    assert consulta(req)=={"encontrado":False}
    assert consulta(req,"email","a@escola.test")["email"]=="a@escola.test"

def test_snapshot_preserva_cadastro_e_nao_segue_alteracao_de_quiz(req):
    c=Lead.objects.create(site_id="s1",email="a@escola.test",phone="96984086018",source="quiz:curso")
    copiar=import_module("apps.core.migrations.0009_contatos_de_acesso").copiar
    copiar(apps,SimpleNamespace(connection=connection))
    c.phone="11999998888"; c.save()
    assert consulta(req)["email"]==c.email
    assert consulta(req,contato="5511999998888")=={"encontrado":False}
    assert Lead.objects.count()==1

def test_sem_admin_recusado(req):
    from ninja.errors import HttpError
    req.auth="outro"
    with pytest.raises(HttpError): consulta(req)


def test_matricula_meshcraft_antiga_e_colisao_entre_formatos(req):
    atual="cc06b8c3-043b-4c06-92c5-5ea624e00586"
    ContatoDeAcesso.objects.create(id=uuid.uuid4(),site_id="Meshcraft",email="antiga@escola.test",telefone="5596984086018")
    assert consulta(req,site=atual)["email"]=="antiga@escola.test"
    assert consulta(req,site="outro")=={"encontrado":False}
    ContatoDeAcesso.objects.create(id=uuid.uuid4(),site_id=atual,email="outra@escola.test",telefone="5596984086018")
    assert consulta(req,site=atual)=={"encontrado":False}
    assert consulta(req,"email","antiga@escola.test",site=atual)["encontrado"]
