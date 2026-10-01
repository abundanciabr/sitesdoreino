import json

import pytest

from apps.matriculas.models import Matricula, Turma


AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
PATH = "/api/alunos/turmas"


@pytest.mark.django_db
def test_turma_draft_publish_and_legacy_enrollment(client, settings):
    settings.TOKENS_ACEITOS = {"editor-token"}
    Matricula.objects.create(
        site_id="escola-a",
        order_id="pedido-1",
        email="a@example.com",
        turma="Turma atual",
        status=Matricula.STATUS_ATIVA,
    )
    listing = client.get(f"{PATH}?site_id=escola-a", **AUTH)
    assert listing.status_code == 200
    assert listing.json()["items"][0]["nome"] == "Turma atual"
    content = {"nome": "Turma 2027", "descricao": "Nova edição"}
    assert (
        client.put(
            f"{PATH}/turma-2027/rascunho?site_id=escola-a",
            data=json.dumps(content),
            content_type="application/json",
        ).status_code
        == 401
    )
    saved = client.put(
        f"{PATH}/turma-2027/rascunho?site_id=escola-a",
        data=json.dumps(content),
        content_type="application/json",
        **AUTH,
    )
    assert saved.status_code == 200
    assert not saved.json()["published"]
    assert not Turma.objects.get(slug="turma-2027").published
    assert Matricula.objects.get(order_id="pedido-1").turma == "Turma atual"
    result = client.post(f"{PATH}/turma-2027/publicar?site_id=escola-a", **AUTH)
    assert result.status_code == 200
    assert result.json()["content"] == content
    assert Turma.objects.get(slug="turma-2027").published
    assert Matricula.objects.get(order_id="pedido-1").turma == "Turma atual"
