# [RECEITA:R10 v1]
import pytest


@pytest.mark.smoke_mensageria
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
