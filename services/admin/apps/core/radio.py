"""O rádio append-only da tríade, dentro da área administrativa."""

import json
import hashlib
import hmac
import re
from pathlib import Path

from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.views.decorators.http import require_GET, require_http_methods

from .models import MensagemDoRadio

_TAREFA = re.compile(r"^TAR-[0-9]{3}$")


def _mensagem_json(mensagem):
    return {
        "sequencia": mensagem.sequencia,
        "autor": mensagem.autor,
        "tipo": mensagem.tipo,
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
    if via_token:
        return _radio_api_autorizada(request)
    return csrf_protect(_radio_api_autorizada)(request)


def _radio_api_autorizada(request):
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
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _erro("o corpo não é JSON válido")
    if not isinstance(dados, dict):
        return _erro("o corpo precisa ser um objeto JSON")
    autor = dados.get("autor")
    tipo = dados.get("tipo", "recado")
    texto = dados.get("texto")
    tarefa = dados.get("tarefa") or ""
    if autor not in MensagemDoRadio.AUTORES:
        return _erro(
            "autor inválido; use claude, codex, antigravity, mantenedor ou fila"
        )
    if tipo not in MensagemDoRadio.TIPOS:
        return _erro("tipo inválido; use recado, parecer ou boletim")
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 2000:
        return _erro("texto precisa ter entre 1 e 2.000 caracteres")
    if not isinstance(tarefa, str) or (tarefa and not _TAREFA.fullmatch(tarefa)):
        return _erro("tarefa precisa ter o formato TAR-NNN")
    try:
        with transaction.atomic():
            dados_mensagem = {
                "autor": autor,
                "tipo": tipo,
                "texto": texto,
                "tarefa": tarefa,
            }
            if autor == "fila" and tipo == "boletim":
                chave = hashlib.sha256(
                    json.dumps([tarefa, texto], ensure_ascii=False).encode()
                ).hexdigest()
                mensagem, criada = MensagemDoRadio.objects.get_or_create(
                    chave_boletim=chave, defaults=dados_mensagem
                )
            else:
                mensagem = MensagemDoRadio.objects.create(**dados_mensagem)
                criada = True
    except (DatabaseError, ValidationError):
        return _erro(
            "não consegui guardar a mensagem; confira o banco e tente de novo", 503
        )
    return JsonResponse(_mensagem_json(mensagem), status=201 if criada else 200)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def radio_pagina(request):
    if request.method == "POST" and request.content_type == "application/json":
        return radio_api(request)
    return csrf_protect(_radio_pagina)(request)


def _radio_pagina(request):
    texto = request.POST.get("texto", "") if request.method == "POST" else ""
    erro_envio = None
    status = 200
    if request.method == "POST":
        if not texto.strip() or len(texto) > 2000:
            erro_envio = (
                "Escreva uma mensagem com 1 a 2.000 caracteres e envie novamente."
            )
            status = 400
        else:
            try:
                with transaction.atomic():
                    MensagemDoRadio.objects.create(autor="mantenedor", texto=texto)
            except (DatabaseError, ValidationError):
                erro_envio = "Não consegui guardar a mensagem. Seu texto foi preservado; confira o banco e tente novamente."
                status = 503
            else:
                return redirect("radio_pagina")
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
            "erro_envio": erro_envio,
            "texto": texto,
        },
        status=status,
    )


@require_GET
def radio_script(request):
    return HttpResponse(
        (Path(__file__).parent / "static" / "radio.js").read_text(encoding="utf-8"),
        content_type="application/javascript; charset=utf-8",
    )
