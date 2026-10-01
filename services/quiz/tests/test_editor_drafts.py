import json

import pytest

from apps.quiz.models import QuizVersion, Submission
from tests.test_smoke import HOST_A, quiz_a, site_a  # noqa: F401


PATH = "/interno/editor/quizzes/crivo"
AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}


@pytest.mark.django_db
def test_draft_is_private_until_publish_and_old_version_survives(
    client, quiz_a, settings
):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    original = quiz_a.versions.get()
    content = {
        "title": "Novo Crivo",
        "questions": [
            {
                "text": "Pergunta nova",
                "options": [{"text": "Não", "points": 0}, {"text": "Sim", "points": 1}],
            }
        ],
        "bands": [{"key": "sim", "title": "Sim", "min_score": 0, "max_score": 1}],
    }
    assert (
        client.put(
            f"{PATH}/rascunho?site_id={quiz_a.site_id}",
            data=json.dumps(content),
            content_type="application/json",
        ).status_code
        == 401
    )
    settings.TOKENS_ACEITOS = {"other-service-token"}
    assert (
        client.get(
            f"{PATH}/rascunho?site_id={quiz_a.site_id}",
            HTTP_AUTHORIZATION="Bearer other-service-token",
        ).status_code
        == 401
    )
    saved = client.put(
        f"{PATH}/rascunho?site_id={quiz_a.site_id}",
        data=json.dumps(content),
        content_type="application/json",
        **AUTH,
    )
    assert saved.status_code == 200
    quiz_a.refresh_from_db()
    assert quiz_a.title == "Crivo"
    assert original.active
    public = client.get("/crivo/", HTTP_HOST=HOST_A)
    assert public.status_code == 200
    assert b"Pergunta 1" in public.content
    assert b"Pergunta nova" not in public.content

    response = client.post(f"{PATH}/publicar?site_id={quiz_a.site_id}", **AUTH)
    assert response.status_code == 200
    quiz_a.refresh_from_db()
    original.refresh_from_db()
    assert quiz_a.title == "Novo Crivo"
    assert not original.active
    assert QuizVersion.objects.filter(quiz=quiz_a, active=True).count() == 1
    assert original.questions.count() == 1
    assert not Submission.objects.exists()


@pytest.mark.django_db
def test_new_quiz_stays_hidden_until_publish(client, site_a, settings):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    content = {
        "title": "Novo",
        "questions": [
            {
                "text": "Pergunta?",
                "options": [{"text": "A", "points": 0}, {"text": "B", "points": 1}],
            }
        ],
        "bands": [{"key": "ok", "title": "OK", "min_score": 0, "max_score": 1}],
    }
    path = "/interno/editor/quizzes/novo"
    assert (
        client.put(
            f"{path}/rascunho?site_id={site_a.pk}",
            data=json.dumps(content),
            content_type="application/json",
            **AUTH,
        ).status_code
        == 200
    )
    assert client.get("/novo/", HTTP_HOST=HOST_A).status_code == 404
    assert (
        client.post(f"{path}/publicar?site_id={site_a.pk}", **AUTH).status_code == 200
    )
    assert client.get("/novo/", HTTP_HOST=HOST_A).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("invalid", ["gap", "javascript"])
def test_invalid_result_does_not_replace_active_version(
    client, quiz_a, settings, invalid
):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    original = quiz_a.versions.get()
    content = {
        "title": "Novo",
        "questions": [
            {
                "text": "Pergunta?",
                "options": [{"text": "A", "points": 0}, {"text": "B", "points": 10}],
            }
        ],
        "bands": [
            {
                "key": "baixo",
                "title": "Baixo",
                "min_score": 0,
                "max_score": 0,
                "botao_destino": "/curso",
                "botao_rotulo": "Abrir",
            },
            {"key": "alto", "title": "Alto", "min_score": 10, "max_score": 10},
        ],
    }
    if invalid == "gap":
        content["bands"][1]["min_score"] = 9
        content["bands"][1]["max_score"] = 9
    else:
        content["bands"][0]["botao_destino"] = "javascript:alert(1)"
    response = client.put(
        f"{PATH}/rascunho?site_id={quiz_a.site_id}",
        data=json.dumps(content),
        content_type="application/json",
        **AUTH,
    )
    assert response.status_code == 422
    original.refresh_from_db()
    assert original.active
    assert quiz_a.versions.count() == 1
    assert b"Pergunta 1" in client.get("/crivo/", HTTP_HOST=HOST_A).content
