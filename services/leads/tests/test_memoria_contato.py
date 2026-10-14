import uuid

import pytest

from apps.core.models import Lead, QuizDoLead, TimelineEvent
from apps.core.memoria_contato import memoria

pytestmark = pytest.mark.django_db


@pytest.fixture
def contato():
    return Lead.objects.create(site_id="site-a", email="teste@example.com", source="quiz")


def test_vinculos_tem_fontes_sem_inferir_identidade_ou_outro_navegador(contato):
    outro = Lead.objects.create(site_id="site-a", email="outro@example.com")
    ev = TimelineEvent.objects.create(lead=contato, event="quiz.completado", payload={
        "visitor_id": "navegador", "quiz_slug": "entrada", "token": "SEGREDO",
        "cpf": "DOCUMENTO", "email": "PRIVADO"})
    TimelineEvent.objects.create(lead=outro, event="quiz.completado", payload={
        "visitor_id": "navegador", "quiz_slug": "NAO_MOSTRAR"})
    QuizDoLead.objects.create(lead=contato, quiz_slug="entrada", sessao="sessao-1", captura_id="captura-1")
    antes = list(TimelineEvent.objects.values())
    m = memoria(contato)
    assert {v["tipo"] for v in m["vinculos"]} == {"Visitante", "Sessão de quiz", "Captura"}
    assert m["eventos"][0]["fonte"] == f"timeline:{ev.pk}"
    assert all(s not in str(m) for s in ("SEGREDO", "DOCUMENTO", "PRIVADO", "NAO_MOSTRAR"))
    assert "não há prova de login" in str(m["lacunas"])
    assert antes == list(TimelineEvent.objects.values())


def test_eventos_divergentes_nao_associam_e_nao_vazam(contato):
    TimelineEvent.objects.create(lead=contato, event="lead.upsert", payload={"site_id": "outro", "visitor_id": "SEGREDO"})
    TimelineEvent.objects.create(lead=contato, event="lead.upsert", payload={"lead_id": str(uuid.uuid4()), "visitor_id": "SEGREDO"})
    m = memoria(contato)
    assert m["vinculos"] == m["eventos"] == []
    assert "SEGREDO" not in str(m)
    assert "2 registro(s) ignorado(s)" in str(m["lacunas"])


def test_limite_e_ordem_explicitos(contato):
    for _ in range(202):
        TimelineEvent.objects.create(lead=contato, event="lead.upsert", payload={})
    m = memoria(contato)
    assert m["cobertura"]["eventos_total"] == 202
    assert m["cobertura"]["eventos_exibidos"] == 200
    assert m["eventos"][0]["fonte"] == "timeline:" + str(contato.timeline.latest("id").pk)
    assert "Cobertura parcial" in str(m["lacunas"])


def test_api_exige_admin_e_site_correto(client, settings, monkeypatch, contato):
    settings.TOKENS_ACEITOS.update({"admin-memoria", "outro-token"})
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-memoria")
    url = f"/api/leads/leads/{contato.pk}/memoria"
    assert client.get(url, {"site_id": "site-a"}).status_code == 401
    assert client.get(url, {"site_id": "site-a"}, HTTP_AUTHORIZATION="Bearer outro-token").status_code == 403
    assert client.get(url, {"site_id": "outro"}, HTTP_AUTHORIZATION="Bearer admin-memoria").status_code == 404
    resposta = client.get(url, {"site_id": "site-a"}, HTTP_AUTHORIZATION="Bearer admin-memoria")
    assert resposta.status_code == 200
    assert resposta["Cache-Control"] == "private, no-store"
    assert resposta.json()["lead_id"] == str(contato.pk)
