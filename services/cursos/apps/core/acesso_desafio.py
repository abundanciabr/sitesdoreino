"""As duas páginas de entrada do Desafio Como Ganhar em Dólar com Roblox.

`acesso-...` é a área do participante, no visual da aula da plataforma de
membros, e `evento-...` é o relógio até a aula 1. As duas são abertas: quem
recebe o link entra sem conta.
"""
from datetime import datetime, timedelta, timezone as tz

from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

CURSO = "desafio-como-ganhar-em-dolar-com-roblox"
NOME = "Desafio Como Ganhar em Dólar com Roblox"
# 19/10/2026, 9h em Brasília (UTC-3, sem horário de verão desde 2019).
AULA_1 = datetime(2026, 10, 19, 9, 0, tzinfo=tz(timedelta(hours=-3)))


@require_GET
@never_cache
def acesso(request):
    return render(request, "cursos/acesso_desafio.html", {"curso": CURSO, "nome": NOME})


@require_GET
@never_cache
def evento(request):
    restante = max(0, int((AULA_1 - timezone.now()).total_seconds()))
    dias, resto = divmod(restante, 86400)
    horas, resto = divmod(resto, 3600)
    minutos, segundos = divmod(resto, 60)
    return render(request, "cursos/evento_desafio.html", {
        "curso": CURSO,
        "nome": NOME,
        "aula_1_iso": AULA_1.isoformat(),
        "liberada": restante == 0,
        "dias": dias,
        "horas": horas,
        "minutos": minutos,
        "segundos": segundos,
    })
