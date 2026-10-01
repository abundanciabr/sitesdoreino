import json

import pytest

from apps.matriculas.models import Matricula, Turma
from apps.matriculas.services import como_o_painel_ve
from apps.matriculas.turmas_publicadas import legacy_slug


AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}
PATH = "/api/alunos/turmas"


@pytest.mark.django_db
def test_turma_draft_publish_and_legacy_enrollment(client, settings):
    settings.TOKENS_ACEITOS = {"editor-token"}
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    settings.TOKENS_ACEITOS.add("other-service-token")
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
    assert (
        client.get(
            f"{PATH}?site_id=escola-a", HTTP_AUTHORIZATION="Bearer other-service-token"
        ).status_code
        == 401
    )
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
    new_member = Matricula.objects.create(
        site_id="escola-a",
        order_id="pedido-2",
        email="b@example.com",
        turma="turma-2027",
        status=Matricula.STATUS_ATIVA,
    )
    assert como_o_painel_ve(new_member)["turma"] == "Turma 2027"


@pytest.mark.django_db
def test_published_legacy_name_reaches_student_views_without_rewriting_access(
    client, settings
):
    settings.TOKENS_ACEITOS = {"editor-token"}
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    original = Matricula.objects.create(
        site_id="escola-a",
        order_id="pedido-1",
        email="a@example.com",
        turma="Turma antiga",
        status=Matricula.STATUS_ATIVA,
    )
    other = Matricula.objects.create(
        site_id="escola-b",
        order_id="pedido-2",
        email="b@example.com",
        turma="Turma antiga",
        status=Matricula.STATUS_ATIVA,
    )
    slug = legacy_slug("Turma antiga")
    draft = {"nome": "Turma renovada", "descricao": "Encontros às terças"}
    path = f"{PATH}/{slug}"
    assert (
        client.put(
            f"{path}/rascunho?site_id=escola-a",
            data=json.dumps(draft),
            content_type="application/json",
            **AUTH,
        ).status_code
        == 200
    )
    before = client.get("/api/alunos/matriculas?site_id=escola-a", **AUTH).json()
    assert before[0]["turma"] == "Turma antiga"
    assert client.get(f"{path}?site_id=escola-a", **AUTH).status_code == 200
    assert client.post(f"{path}/publicar?site_id=escola-a", **AUTH).status_code == 200
    after = client.get("/api/alunos/matriculas?site_id=escola-a", **AUTH).json()
    assert after[0]["turma"] == "Turma renovada"
    page = client.get("/api/alunos/matriculas/pagina?site_id=escola-a", **AUTH).json()
    assert page["itens"][0]["turma"] == "Turma renovada"
    record = client.get("/api/alunos/alunos/a@example.com/prontuario", **AUTH).json()
    assert record["turma"] == "Turma renovada"
    assert record["passagens"][0]["turma"] == "Turma renovada"
    published = client.get(f"{path}?site_id=escola-a", **AUTH).json()
    assert published["content"] == draft
    assert (
        client.get("/api/alunos/matriculas?site_id=escola-b", **AUTH).json()[0]["turma"]
        == "Turma antiga"
    )
    original.refresh_from_db()
    other.refresh_from_db()
    assert original.turma == other.turma == "Turma antiga"
    assert original.status == other.status == Matricula.STATUS_ATIVA
