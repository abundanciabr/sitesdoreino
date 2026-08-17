# [RECEITA:R10 v1]
import pytest


@pytest.mark.smoke_alunos
def test_healthz_responde_200(client):
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


@pytest.fixture
def token_valido(settings):
    settings.TOKENS_ACEITOS = {"token-de-teste"}
    return "token-de-teste"


def test_superficie_create_enrollment_ainda_nao_implementada(client, token_valido):
    """Fase 0 — esqueleto: a superfície existe (espelha o contrato congelado),
    mas os handlers ainda respondem 501 (regra de negócio real é fora de escopo)."""
    resp = client.post(
        "/api/alunos/matriculas",
        data="{}",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_superficie_list_enrollments_ainda_nao_implementada(client, token_valido):
    resp = client.get(
        "/api/alunos/alunos/aluno@example.com/matriculas",
        HTTP_AUTHORIZATION=f"Bearer {token_valido}",
    )
    assert resp.status_code == 501


def test_superficie_sem_token_e_401(client):
    resp = client.post(
        "/api/alunos/matriculas", data="{}", content_type="application/json"
    )
    assert resp.status_code == 401
