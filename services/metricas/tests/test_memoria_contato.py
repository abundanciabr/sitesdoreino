import uuid
import pytest
from django.utils import timezone
from apps.fatos.models import Evento
from apps.fatos.memoria_contato import memoria

pytestmark = pytest.mark.django_db


def fato(site, lead, visitante="v1", tipo="funil.lead-capturado"):
    return Evento.objects.create(event_id=uuid.uuid4(), tipo=tipo, versao=1,
        celula=tipo.split(".")[0], site_id=site, ocorrido_em=timezone.now(),
        dados={"lead_id": lead, "visitor_id": visitante, "email": "NAO_EXIBIR"})


def test_so_fatos_deste_site_e_lead_sem_expandir_navegador():
    lead = str(uuid.uuid4())
    esperado = fato("a", lead)
    fato("b", lead)
    fato("a", str(uuid.uuid4()))
    fato("a", "", tipo="funil.pagina-vista")
    m = memoria("a", lead)
    assert m["total"] == m["exibidos"] == 1
    assert m["eventos"][0]["event_id"] == str(esperado.event_id)
    assert m["vinculos"][0]["valor"] == "v1"
    assert "NAO_EXIBIR" not in str(m)


def test_api_so_admin(client, settings, monkeypatch):
    settings.TOKENS_ACEITOS.update({"admin-memoria", "leitor"})
    monkeypatch.setenv("TOKENS_ACEITOS_ADMIN", "admin-memoria")
    url = f"/api/metricas/contatos/{uuid.uuid4()}/memoria"
    assert client.get(url, {"site_id": "a"}).status_code == 401
    assert client.get(url, {"site_id": "a"}, HTTP_AUTHORIZATION="Bearer leitor").status_code == 403
    r = client.get(url, {"site_id": "a"}, HTTP_AUTHORIZATION="Bearer admin-memoria")
    assert r.status_code == 200 and r.json()["total"] == 0
