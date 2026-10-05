import pytest
from apps.core.models import Lead, TimelineEvent
from apps.core.origem_contato import origem_do_contato, origens_das_pessoas

pytestmark = pytest.mark.django_db


def test_primeira_origem_e_campanha_sobrevivem_a_cadastro_posterior():
    lead = Lead.objects.create(site_id="s", email="aluna@dominio.com", source="crm")
    TimelineEvent.objects.create(lead=lead, event="lead.upsert", payload={
        "source": "quiz:crivo", "utm": {"source": "instagram", "campaign": "entrada"}})
    TimelineEvent.objects.create(lead=lead, event="lead.upsert", payload={"source": "crm"})
    origem = origem_do_contato(lead)
    assert origem["venda_origem"] == "quiz"
    assert origem["origem_registrada"] == "quiz:crivo"
    assert origem["campanha"] == "instagram · entrada"
    assert origens_das_pessoas([{"id": "1", "email": lead.email, "site_id": "outro"}]) == {}


@pytest.mark.parametrize("source,utm,esperada", [
    ("", {}, "desconhecida"), ("indicacao", {}, "outros"),
    ("crm", {}, "crm"), ("landing", {"utm_source": "google"}, "trafego"),
])
def test_sem_evidencia_nao_chama_tudo_de_crm(source, utm, esperada):
    lead = Lead.objects.create(site_id="s", email="aluna@dominio.com", source=source, utm=utm)
    assert origem_do_contato(lead)["venda_origem"] == esperada


def test_importacao_da_escola_nao_vira_origem_quiz_depois():
    lead = Lead.objects.create(site_id="s", email="aluna@dominio.com", source="escola")
    TimelineEvent.objects.create(lead=lead, event="aluno.matricula", payload={})
    TimelineEvent.objects.create(lead=lead, event="quiz.completado", payload={"quiz_slug": "novo"})
    assert origem_do_contato(lead)["origem_registrada"] == "escola"
