import json
import uuid

import pytest
from django.utils import timezone

from apps.core.models import CompraDaOportunidade, Lead, TimelineEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def painel(settings, monkeypatch):
    settings.TOKENS_ACEITOS.add("admin-suporte")
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-suporte")
    return {"HTTP_AUTHORIZATION": "Bearer admin-suporte"}


@pytest.fixture
def lead():
    return Lead.objects.create(site_id="escola-a", email="marina@dominio.com", name="Marina")


def _interesse(client, lead_id, painel, **dados):
    corpo = {"produto_id": "prod-desafio", "produto": "Desafio Roblox", "referencia": "conversa-1", "autor": "Equipe", **dados}
    return client.post(f"/api/leads/leads/{lead_id}/interesses", json.dumps(corpo),
                       content_type="application/json", **painel)


def test_interesse_vira_historico_e_tag_sem_duplicar(client, painel, lead):
    assert _interesse(client, lead.id, painel).json() == {"registrado": True, "tag": "interesse:prod-desafio"}
    assert _interesse(client, lead.id, painel).json()["registrado"] is False
    lead.refresh_from_db()
    assert lead.tags.count("interesse:prod-desafio") == 1
    evento = TimelineEvent.objects.get(lead=lead, event="interesse.registrado")
    assert evento.payload["produto"] == "Desafio Roblox" and evento.payload["origem"] == "suporte"


def test_interesse_exige_painel_lead_existente_e_produto(client, painel, lead, settings):
    settings.TOKENS_ACEITOS.add("outro-par")
    assert _interesse(client, lead.id, {"HTTP_AUTHORIZATION": "Bearer outro-par"}).status_code == 403
    assert _interesse(client, uuid.uuid4(), painel).status_code == 404
    assert _interesse(client, lead.id, painel, produto="").status_code == 422
    assert not TimelineEvent.objects.filter(event="interesse.registrado").exists()


def test_ficha_do_painel_traz_compras_reais(client, painel, lead):
    CompraDaOportunidade.objects.create(site_id="escola-a", pedido_id="p-1", lead=lead, produtos=["prod-desafio"],
        valor_pedido_centavos=9700, aprovado_em=timezone.now(), valor_aprovado_centavos=9700)
    CompraDaOportunidade.objects.create(site_id="escola-a", pedido_id="p-teste", lead=lead, sandbox=True)
    compras = client.get(f"/api/leads/leads/{lead.id}", **painel).json()["compras"]
    assert [(c["pedido"], c["situacao"], c["valor_centavos"], c["produtos"]) for c in compras] == [
        ("p-1", "aprovada", 9700, ["prod-desafio"])]
