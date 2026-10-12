from django.http import JsonResponse
from django.urls import path

from config.api import api
from apps.core.hotmart import teste as hotmart_teste
from apps.matriculas.editor_turmas import (
    turmas,
    turma_draft,
    publish_turma,
    turma_publicada,
)


def healthz(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("api/alunos/hotmart/testes", hotmart_teste),
    path("healthz", healthz),
    path("api/alunos/turmas", turmas),
    path("api/alunos/turmas/<slug:slug>/rascunho", turma_draft),
    path("api/alunos/turmas/<slug:slug>/publicar", publish_turma),
    path("api/alunos/turmas/<slug:slug>", turma_publicada),
    path("api/alunos/", api.urls),
]
