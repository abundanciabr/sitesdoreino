import json
import os
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

import pytest
from django.core import signing

from apps.quiz.management.commands.seed_laboratorio_crivo import semear_laboratorio
from apps.quiz.models import Site, Submission
from apps.quiz.views import SALT_SESSAO

pytestmark = pytest.mark.django_db(transaction=True)


def test_laboratorio_no_celular_computador_e_teclado(live_server):
    site = Site.objects.create(
        id="laboratorio-e2e", host="localhost", name="Laboratório E2E"
    )
    quiz = semear_laboratorio(site)
    cookies = []
    for indice in range(6):
        versao = quiz.versions.get(key="conversa" if indice % 3 == 1 else "original")
        cookies.append(
            signing.dumps(
                {
                    "quizzes": {
                        quiz.slug: {
                            "site_id": site.id,
                            "session_id": str(uuid.uuid4()),
                            "version_id": versao.id,
                            "version_key": versao.key,
                            "utm": {
                                "source": "laboratorio",
                                "campaign": quiz.slug,
                                "content": "foco",
                            },
                        }
                    }
                },
                salt=SALT_SESSAO,
            )
        )
    ambiente = {
        k: v
        for k, v in os.environ.items()
        if k
        in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "TEMP",
            "TMP",
            "PLAYWRIGHT_BROWSERS_PATH",
            "NODE_PATH",
        )
    }
    ambiente["LAB_COOKIES"] = json.dumps(cookies)
    telas = Path(tempfile.gettempdir()) / "laboratorio-crivo-telas"
    telas.mkdir(exist_ok=True)
    ambiente["LAB_PROVAS"] = str(telas)
    resultado = subprocess.run(
        [
            shutil.which("node"),
            str(Path(__file__).with_name("laboratorio_browser.js")),
            live_server.url,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
        timeout=180,
    )
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    provas = json.loads(resultado.stdout.splitlines()[-1])
    assert len(provas) == 7
    assert provas[-1]["semJavaScript"]
    assert set(
        Submission.objects.filter(quiz=quiz).values_list("score", flat=True)
    ) == {0, 3, 6}
    print(json.dumps(provas, ensure_ascii=False))
