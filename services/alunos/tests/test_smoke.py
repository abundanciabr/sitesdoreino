# [RECEITA:R10 v1]
import json

import pytest

from apps.matriculas.models import Matricula


@pytest.mark.smoke_alunos
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


@pytest.mark.django_db
def test_create_enrollment_cria_matricula(client, token_valido):
    resp = client.post(
        "/api/alunos/matriculas",
        data=json.dumps(
            {
                "site_id": "site-1",
                "order_id": "order-abc",
                "product_id": "prod-1",
                "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
            }
        ),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 201
    assert resp.json()["order_id"] == "order-abc"


@pytest.mark.django_db
def test_create_enrollment_e_idempotente_por_order_id(client, token_valido):
    corpo = json.dumps(
        {
            "site_id": "site-1",
            "order_id": "order-repetido",
            "product_id": "prod-1",
            "customer": {"email": "aluno@example.com", "name": "Aluno Exemplo"},
        }
    )
    r1 = client.post(
        "/api/alunos/matriculas",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    r2 = client.post(
        "/api/alunos/matriculas",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert r1.status_code == 201
    assert r2.status_code == 200
    assert Matricula.objects.filter(order_id="order-repetido").count() == 1


@pytest.mark.django_db
def test_create_enrollment_payload_invalido_e_422(client, token_valido):
    resp = client.post(
        "/api/alunos/matriculas",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 422


@pytest.mark.django_db
def test_list_enrollments_devolve_matriculas_do_aluno(client, token_valido):
    Matricula.objects.create(
        site_id="site-1",
        order_id="order-list-1",
        product_id="prod-1",
        email="aluno-lista@example.com",
        name="Aluno Lista",
    )
    Matricula.objects.create(
        site_id="site-2",
        order_id="order-list-2",
        product_id="",
        email="aluno-lista@example.com",
        name="Aluno Lista",
    )
    resp = client.get(
        "/api/alunos/alunos/aluno-lista@example.com/matriculas",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 200
    corpo = resp.json()
    assert len(corpo) == 2
    assert {m["order_id"] for m in corpo} == {"order-list-1", "order-list-2"}
    assert corpo[0]["status"] == "ativa"


@pytest.mark.django_db
def test_list_enrollments_sem_matricula_e_404(client, token_valido):
    resp = client.get(
        "/api/alunos/alunos/aluno-sem-matricula@example.com/matriculas",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 404


def test_superficie_sem_token_e_401(client):
    resp = client.post(
        "/api/alunos/matriculas", data="{}", content_type="application/json"
    )
    assert resp.status_code == 401
