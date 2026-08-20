# tests/test_leads_upsert.py  # [RECEITA:R1 v1]
import json

import pytest

from apps.core.models import Lead, TimelineEvent

pytestmark = pytest.mark.django_db


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def _post_lead(client, token, **body):
    return client.post(
        "/api/leads/leads",
        data=json.dumps(body),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token}",
    )


def test_upsert_cria_lead_novo(client, token_valido):
    resp = _post_lead(
        client, token_valido, site_id="site-a", email="ana@example.com", name="Ana"
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert corpo["created"] is True
    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert corpo["lead_id"] == str(lead.id)


def test_upsert_por_email_nao_duplica_lead(client, token_valido):
    primeira = _post_lead(
        client, token_valido, site_id="site-a", email="ana@example.com", name="Ana"
    )
    segunda = _post_lead(
        client,
        token_valido,
        site_id="site-a",
        email="ana@example.com",
        phone="11999999999",
    )

    assert primeira.json()["created"] is True
    assert segunda.json()["created"] is False
    assert primeira.json()["lead_id"] == segunda.json()["lead_id"]
    assert Lead.objects.filter(site_id="site-a", email="ana@example.com").count() == 1

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert lead.phone == "11999999999"
    assert lead.name == "Ana"  # preservado — 2ª chamada não mandou name


def test_mesma_pessoa_em_sites_diferentes_gera_leads_distintos(client, token_valido):
    _post_lead(client, token_valido, site_id="site-a", email="ana@example.com")
    _post_lead(client, token_valido, site_id="site-b", email="ana@example.com")

    assert Lead.objects.filter(email="ana@example.com").count() == 2


def test_upsert_sem_email_e_422(client, token_valido):
    resp = _post_lead(client, token_valido, site_id="site-a")
    assert resp.status_code == 422


def test_upsert_repetido_preserva_timeline_anterior(client, token_valido):
    """[invariante da célula] merge de pessoa nunca deleta histórico."""
    _post_lead(
        client, token_valido, site_id="site-a", email="ana@example.com", source="lp-1"
    )
    _post_lead(
        client, token_valido, site_id="site-a", email="ana@example.com", source="lp-2"
    )

    lead = Lead.objects.get(site_id="site-a", email="ana@example.com")
    assert TimelineEvent.objects.filter(lead=lead, event="lead.upsert").count() == 2
