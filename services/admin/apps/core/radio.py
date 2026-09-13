"""O rádio append-only da tríade, dentro da área administrativa."""

import json
import hmac
import re

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt

from .models import MensagemDoRadio

_TAREFA = re.compile(r"^TAR-[0-9]{3}$")


def _mensagem_json(mensagem):
    return {
        "sequencia": mensagem.sequencia,
        "autor": mensagem.autor,
        "quando": mensagem.quando.isoformat(),
        "texto": mensagem.texto,
        "tarefa": mensagem.tarefa or None,
    }


def _erro(mensagem, status=400):
    return JsonResponse(
        {"erro": mensagem, "como_corrigir": "corrija o JSON e tente de novo"},
        status=status,
    )


@csrf_exempt
def radio_api(request):
    if request.method not in {"GET", "POST"}:
        return _erro("método não permitido; use GET ou POST", 405)
    cracha = request.headers.get("Authorization", "")
    token = cracha.removeprefix("Bearer ")
    via_token = bool(token) and hmac.compare_digest(token, settings.ADMIN_RADIO_TOKEN)
    if not getattr(request, "admin", None) and not via_token:
        return _erro("crachá de administrador ausente", 403)
    if request.method == "GET":
        try:
            desde = int(request.GET.get("desde", "0"))
            if desde < 0:
                raise ValueError
        except ValueError:
            return _erro("desde precisa ser um número inteiro maior ou igual a zero")
        mensagens = MensagemDoRadio.objects.filter(sequencia__gt=desde).order_by(
            "sequencia"
        )
        itens = [_mensagem_json(item) for item in mensagens]
        return JsonResponse(
            {
                "mensagens": itens,
                "ultima_sequencia": itens[-1]["sequencia"] if itens else desde,
            }
        )

    try:
        dados = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return _erro("o corpo não é JSON válido")
    autor = dados.get("autor")
    texto = dados.get("texto")
    tarefa = dados.get("tarefa") or ""
    if autor not in MensagemDoRadio.AUTORES:
        return _erro("autor inválido; use claude, codex, antigravity ou mantenedor")
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 2000:
        return _erro("texto precisa ter entre 1 e 2.000 caracteres")
    if tarefa and not _TAREFA.fullmatch(tarefa):
        return _erro("tarefa precisa ter o formato TAR-NNN")
    try:
        with transaction.atomic():
            mensagem = MensagemDoRadio.objects.create(
                autor=autor, texto=texto, tarefa=tarefa
            )
    except (DatabaseError, ValidationError):
        return _erro(
            "não consegui guardar a mensagem; confira o banco e tente de novo", 503
        )
    return JsonResponse(_mensagem_json(mensagem), status=201)


def radio_pagina(request):
    try:
        mensagens = list(MensagemDoRadio.objects.order_by("sequencia"))
        erro = None
    except DatabaseError:
        mensagens = []
        erro = "Não consegui carregar o rádio. Confira o banco e recarregue a página."
    return render(
        request,
        "admin/radio.html",
        {
            "mensagens": [_mensagem_json(item) for item in mensagens],
            "ultima_sequencia": mensagens[-1].sequencia if mensagens else 0,
            "erro": erro,
        },
    )
