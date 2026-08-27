from django.http import JsonResponse
from django.urls import path


def healthz(request):
    return JsonResponse({"status": "ok"})


# Só o `/healthz`, e isso é a gênese fazendo o que a lei mandou: a célula nasce
# SEM TELA e SEM superfície de máquina (`DECISAO-notificacoes` §1.1 — nasce
# `freeze: not-applicable` e só congela contrato quando alguém for consumi-la).
# Quem vai perguntar "quantos avisos eu tenho" é o `funil`, na Fase 4, que é
# Rito de Contrato com o mantenedor presente. Acrescentar a rota antes disso
# seria fabricar a fronteira dentro de um despacho.
urlpatterns = [
    path("healthz", healthz),
]
