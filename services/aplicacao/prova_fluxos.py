"""Fluxo editorial real na aplicação única, em bancos efêmeros da prova.

Chamado por prova.py depois das migrações e da instalação do transporte HTTP
interno. Os valores, usuários e conteúdos abaixo são inteiramente sintéticos.
"""

from __future__ import annotations

import asyncio

import httpx

from config.runtime import serving


SLUG = "prova-fluxo-unico"
SITE_ID = "prova-fluxo-unico"
TOKEN = "prova-editor-quiz"


def _semear():
    from modules.quiz.apps.quiz.models import (
        Option, Question, Quiz, QuizVersion, ResultBand, Site,
    )

    with serving("quiz"):
        site = Site.objects.create(
            id=SITE_ID, host="meshcraft.top", name="Prova isolada", active=True
        )
        quiz = Quiz.objects.create(
            site=site, slug=SLUG, title="Antes da publicação", active=True
        )
        antiga = QuizVersion.objects.create(
            quiz=quiz, key="anterior", weight=100, active=True
        )
        pergunta = Question.objects.create(
            version=antiga, order=1, text="Pergunta anterior"
        )
        Option.objects.create(
            question=pergunta, order=1, text="Não", points=0
        )
        Option.objects.create(
            question=pergunta, order=2, text="Sim", points=1
        )
        ResultBand.objects.create(
            version=antiga, key="anterior", title="Anterior",
            min_score=0, max_score=1,
        )
        return quiz.pk, antiga.pk


async def _exercitar_http():
    import config.asgi

    payload = {
        "title": "Depois da publicação",
        "questions": [{
            "text": "Pergunta nova",
            "options": [
                {"text": "Não", "points": 0},
                {"text": "Sim", "points": 1},
            ],
        }],
        "bands": [{
            "key": "nova", "title": "Nova",
            "min_score": 0, "max_score": 1,
        }],
    }
    private = f"/interno/editor/quizzes/{SLUG}"
    public = f"/quiz/{SLUG}/"
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=config.asgi.application),
        base_url="https://meshcraft.top", follow_redirects=False,
    ) as site:
        for method, path in (
            ("GET", "/admin/conteudos/quiz/"),
            ("POST", f"/admin/conteudos/quiz/{SLUG}/publicar"),
        ):
            response = await site.request(method, path)
            if response.status_code not in (302, 403, 404):
                raise AssertionError(
                    f"admin anônimo alcançou {path}: HTTP {response.status_code}"
                )

        before = await site.get(public)
        if before.status_code != 200 or b"Pergunta anterior" not in before.content:
            raise AssertionError(f"quiz inicial não abriu: HTTP {before.status_code}")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=config.asgi.app_do_servico("quiz")),
        base_url="http://quiz:8000", follow_redirects=False,
    ) as editor:
        query = {"site_id": SITE_ID}
        route = private + "/rascunho"
        unauthorized = await editor.put(route, params=query, json=payload)
        other = await editor.put(
            route, params=query, json=payload,
            headers={"Authorization": "Bearer token-de-outro-servico"},
        )
        if (unauthorized.status_code, other.status_code) != (401, 401):
            raise AssertionError("editor aceitou visitante ou token de outro módulo")
        saved = await editor.put(
            route, params=query, json=payload,
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        if saved.status_code != 200 or not saved.json().get("has_draft"):
            raise AssertionError(f"rascunho sintético não foi salvo: HTTP {saved.status_code}")

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=config.asgi.application),
            base_url="https://meshcraft.top",
        ) as site:
            during = await site.get(public)
        if during.status_code != 200 or b"Pergunta nova" in during.content:
            raise AssertionError("rascunho vazou para a página pública")
        if b"Pergunta anterior" not in during.content:
            raise AssertionError("rascunho retirou a versão publicada")

        published = await editor.post(
            private + "/publicar", params=query,
            headers={"Authorization": f"Bearer {TOKEN}"},
        )
        if published.status_code != 200 or published.json().get("has_draft"):
            raise AssertionError(f"publicação sintética falhou: HTTP {published.status_code}")

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=config.asgi.application),
        base_url="https://meshcraft.top",
    ) as site:
        after = await site.get(public)
        if after.status_code != 200 or b"Pergunta nova" not in after.content:
            raise AssertionError(f"quiz publicado não abriu: HTTP {after.status_code}")


def provar() -> None:
    from modules.quiz.apps.quiz.models import Quiz, QuizVersion

    quiz_id, antiga_id = _semear()
    asyncio.run(_exercitar_http())
    with serving("quiz"):
        quiz = Quiz.objects.get(pk=quiz_id)
        old = QuizVersion.objects.get(pk=antiga_id)
        if quiz.title != "Depois da publicação" or old.active:
            raise AssertionError("publicação não trocou a versão ativa")
        if quiz.versions.filter(active=True).count() != 1:
            raise AssertionError("quiz não tem exatamente uma versão ativa")
        if old.questions.count() != 1 or hasattr(quiz, "draft"):
            raise AssertionError("versão anterior foi perdida ou rascunho não foi consumido")


if __name__ == "__main__":
    provar()
