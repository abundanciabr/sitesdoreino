from django.http import JsonResponse
from django.urls import path

from config.api import api


def healthz(request):
    return JsonResponse({"status": "ok"})


# A gênese nasceu só com `/healthz` — a lei mandava assim
# (`DECISAO-notificacoes` §1.1: `freeze: not-applicable` até alguém consumir a
# célula). Isso mudou na Fase 4 (`contracts/notificacoes.openapi.yaml`, Rito de
# Contrato de 27/08/2026, PR #274): o manifesto virou `freeze: required`, e
# `api.urls` é a porta de consulta que o `funil` e a própria `sugestoes` vão
# chamar. Prefixo `api/notificacoes/` casa com `servers` do contrato
# congelado — mesma convenção de `alunos`/`catalogo` (`api/<celula>/`).
urlpatterns = [
    path("healthz", healthz),
    path("api/notificacoes/", api.urls),
]
