from types import SimpleNamespace
from uuid import uuid4

import pytest
from ninja.errors import HttpError

from apps.core.jornada_acesso import ConsultaRecuperacaoWhatsApp, resolver_whatsapp
from apps.matriculas.models import Matricula

SITE = "cc06b8c3-043b-4c06-92c5-5ea624e00586"
EMAIL = "aluna@example.test"

def matricula(email=EMAIL, status="ativa", whatsapp="(15) 99999-9122", site="Meshcraft"):
    return Matricula.objects.create(
        order_id=str(uuid4()), site_id=site, email=email, name="Pessoa de teste",
        whatsapp=whatsapp, status=status,
    )

@pytest.fixture
def consultar(monkeypatch):
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "token-local")
    def consulta(email="", auth="token-local"):
        return resolver_whatsapp(
            SimpleNamespace(auth=auth),
            ConsultaRecuperacaoWhatsApp(site_id=SITE, telefone="+55 (15) 99999-9122", email_da_ficha=email),
        )
    return consulta

@pytest.mark.django_db
def test_matricula_ativa_sem_ficha(consultar):
    matricula()
    matricula(email="outra@example.test", site="outro-site")
    assert consultar() == {"encontrado": True, "email": EMAIL, "destino": "5515999999122"}

@pytest.mark.django_db
@pytest.mark.parametrize("status", ["suspensa", "encerrada", "reembolsada", "aguardando", "recusada"])
def test_status_sem_acesso(consultar, status):
    matricula(status=status)
    assert not consultar(EMAIL)["encontrado"]

@pytest.mark.django_db
def test_numero_compartilhado_ou_ficha_divergente(consultar):
    matricula()
    assert not consultar("outra@example.test")["encontrado"]
    matricula(email="outra@example.test")
    assert not consultar()["encontrado"]

@pytest.mark.django_db
def test_ficha_legada_com_matricula_ativa_sem_telefone(consultar):
    linha = matricula(whatsapp="")
    assert consultar(EMAIL)["encontrado"]
    linha.whatsapp = "5515999990000"
    linha.save(update_fields=["whatsapp"])
    assert not consultar(EMAIL)["encontrado"]

def test_endpoint_nao_aceita_outro_consumidor(consultar):
    with pytest.raises(HttpError) as erro:
        consultar(auth="outro-token")
    assert erro.value.status_code == 403
