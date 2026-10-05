from datetime import timedelta
import json

import pytest
from django.utils import timezone

from apps.core.conversoes_alunos import vinculos_comerciais
from apps.core.models import Lead

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("fonte,utm,esperada", [
    ("quiz:entrada", {}, "quiz"), ("landing", {"utm_source": "ads"}, "trafego"),
    ("crm", {}, "crm"), ("escola", {}, None), ("sandbox", {}, None), ("", {}, None),
])
def test_so_contatos_comerciais_anteriores_contam(fonte, utm, esperada):
    lead = Lead.objects.create(site_id="site", email="Maria@dominio.com", source=fonte, utm=utm)
    pessoa = {"id": "m1", "site_id": "site", "email": "maria@dominio.com",
              "virou_aluno_em": (timezone.now() + timedelta(seconds=1)).isoformat()}
    resultado = vinculos_comerciais([pessoa])
    if esperada:
        assert resultado["m1"] == {"contato_crm_id": str(lead.pk), "venda_origem": esperada}
    else:
        assert resultado == {}
    assert vinculos_comerciais([{**pessoa, "site_id": "outro"}]) == {}
    assert vinculos_comerciais([{**pessoa, "virou_aluno_em": (lead.created_at - timedelta(seconds=1)).isoformat()}]) == {}


def test_porta_so_painel_sem_criar_contato(client, settings, monkeypatch):
    settings.TOKENS_ACEITOS.update({"painel", "outro"})
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "painel")
    payload = {"pessoas": [{"id": "1", "site_id": "site", "email": "ausente@dominio.com"}]}
    url = "/api/leads/alunos/vinculos-comerciais"
    assert client.post(url, json.dumps(payload), content_type="application/json", HTTP_AUTHORIZATION="Bearer outro").status_code == 403
    resposta = client.post(url, json.dumps(payload), content_type="application/json", HTTP_AUTHORIZATION="Bearer painel")
    assert resposta.status_code == 200
    assert resposta.json() == {"vinculos": {}}
    assert Lead.objects.count() == 0
