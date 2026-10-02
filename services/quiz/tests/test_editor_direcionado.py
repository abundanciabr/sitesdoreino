import copy
import json

import pytest

from apps.quiz.destinos import conectar_checkouts
from apps.quiz.models import Quiz, QuizVersion
from tests.test_importar_quiz import documento, site  # noqa: F401


AUTH = {"HTTP_AUTHORIZATION": "Bearer editor-token"}


def _path(document, site):
    return f"/interno/editor/quizzes/{document['quiz']['slug']}?site_id={site.pk}"


@pytest.mark.django_db
def test_editor_direcionado_publica_versoes_sem_mudar_as_anteriores(
    client, settings, site, documento
):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    path = _path(documento, site)
    draft = client.put(
        path.replace("?", "/rascunho?"),
        data=json.dumps(documento),
        content_type="application/json",
        **AUTH,
    )
    assert draft.status_code == 200
    quiz = Quiz.objects.get(site=site, slug=documento["quiz"]["slug"])
    assert quiz.directed and not quiz.active and quiz.versions.count() == 0
    assert client.post(path.replace("?", "/publicar?"), **AUTH).status_code == 200
    first = QuizVersion.objects.get(quiz=quiz, key="B2")
    assert (
        first.active
        and first.experience["documento"]["versao"] == documento["versoes"][0]
    )
    checkouts = {
        "curso-inicial": "https://exemplo.com/inicial",
        "curso-avancado": "https://exemplo.com/avancado",
    }
    conectar_checkouts(quiz, checkouts)

    expanded = copy.deepcopy(documento)
    expanded["versoes"].append(copy.deepcopy(expanded["versoes"][0]))
    expanded["versoes"][1]["key"] = "A"
    assert (
        client.put(
            path.replace("?", "/rascunho?"),
            data=json.dumps(expanded),
            content_type="application/json",
            **AUTH,
        ).status_code
        == 200
    )
    first.refresh_from_db()
    assert first.experience["documento"]["versao"] == documento["versoes"][0]
    assert client.post(path.replace("?", "/publicar?"), **AUTH).status_code == 200
    assert set(quiz.versions.filter(active=True).values_list("key", flat=True)) == {
        "B2",
        "A",
    }
    first.refresh_from_db()
    assert first.experience["documento"]["versao"] == documento["versoes"][0]
    for version in quiz.versions.all():
        assert {
            key: offer["checkout_url"]
            for key, offer in version.experience["ofertas"].items()
        } == checkouts

    changed = copy.deepcopy(expanded)
    changed["versoes"][0]["perguntas"][0]["texto"] = "Alteração indevida"
    assert (
        client.put(
            path.replace("?", "/rascunho?"),
            data=json.dumps(changed),
            content_type="application/json",
            **AUTH,
        ).status_code
        == 200
    )
    assert client.post(path.replace("?", "/publicar?"), **AUTH).status_code == 422
    assert set(quiz.versions.filter(active=True).values_list("key", flat=True)) == {
        "B2",
        "A",
    }
    assert quiz.draft.content == changed


@pytest.mark.django_db
def test_editor_nao_converte_slug_legado_em_campanha(client, settings, site, documento):
    settings.TOKEN_EDITOR_ADMIN = "editor-token"
    Quiz.objects.create(site=site, slug=documento["quiz"]["slug"], title="Legado")
    response = client.put(
        _path(documento, site).replace("?", "/rascunho?"),
        data=json.dumps(documento),
        content_type="application/json",
        **AUTH,
    )
    assert response.status_code == 422
