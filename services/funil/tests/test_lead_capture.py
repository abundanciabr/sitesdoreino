import json

from tests.conftest import HOST_A, HOST_DESCONHECIDO, SITE_A


def _post(client, corpo, host=HOST_A):
    return client.post(
        "/leads",
        data=json.dumps(corpo),
        content_type="application/json",
        HTTP_HOST=host,
    )


def test_captura_lead_repassa_site_id_resolvido_pelo_conv_site_e_utm(client, rede):
    resp = _post(
        client,
        {
            "email": "cliente@exemplo.com",
            "name": "Cliente",
            "utm": {"utm_source": "instagram"},
        },
    )
    assert resp.status_code == 200, resp.content
    assert resp.json() == {"lead_id": "lead-de-teste", "created": True}

    enviado = json.loads(rede.calls.last.request.content)
    assert (
        enviado["site_id"] == SITE_A["id"]
    )  # [INV-P11] site vem do Host, não do payload
    assert enviado["email"] == "cliente@exemplo.com"
    assert enviado["utm"] == {"utm_source": "instagram"}


def test_email_ausente_e_422(client, rede):
    resp = _post(client, {"name": "Sem e-mail"})
    assert resp.status_code == 422
    # o CONV-SITE resolve o site ANTES da view (bate no catálogo sempre); o que
    # não pode acontecer é a chamada a leads sem e-mail.
    chamadas_a_leads = [c for c in rede.calls if "/leads" in str(c.request.url)]
    assert chamadas_a_leads == []


def test_captura_lead_host_desconhecido_e_404(client, rede):
    resp = _post(client, {"email": "cliente@exemplo.com"}, host=HOST_DESCONHECIDO)
    assert resp.status_code == 404
