"""Recuperação por link entregue no canal de atendimento já ligado ao aluno."""

import hashlib
import hmac
import re
import uuid
from datetime import timedelta

from django.contrib.auth.hashers import make_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from ninja import Router, Schema
from ninja.errors import HttpError
from django.conf import settings

from apps.identidade.models import Identidade, RecuperacaoSenha


PRAZO = timedelta(minutes=30)
FORMA_TOKEN = re.compile(r"\A[0-9a-f]{32}\.[0-9a-f]{64}\Z")
router = Router()


class PedidoDeRecuperacao(Schema):
    id: str
    chave_idempotencia: str


class LinkDeRecuperacao(Schema):
    caminho: str
    expira_em: str


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _token_da_linha(linha_id: uuid.UUID) -> str:
    assinatura = hmac.new(settings.SECRET_KEY.encode("utf-8"),
                          b"recuperacao-senha-v1:" + linha_id.bytes, hashlib.sha256).hexdigest()
    return f"{linha_id.hex}.{assinatura}"


@router.post("/pessoas/solicitar-recuperacao", response=LinkDeRecuperacao,
             operation_id="solicitarRecuperacaoSenha")
def solicitar_recuperacao(request, corpo: PedidoDeRecuperacao):
    # O consumidor resolve a pessoa por uma ficha vinculada à conversa. Não se
    # aceita e-mail arbitrário, nem se cria uma identidade neste fluxo.
    if request.auth not in settings.TOKENS_SENHA or request.auth not in settings.TOKENS_COMPLETOS:
        raise HttpError(403, "este par não está autorizado a recuperar senha")
    identidade = Identidade.objects.filter(pk=corpo.id.strip()).first()
    if identidade is None:
        raise HttpError(404, "identidade não encontrada")
    chave = corpo.chave_idempotencia.strip()
    if not chave or len(chave) > 100:
        raise HttpError(422, "chave_idempotencia obrigatoria (ate 100 caracteres)")
    pedido_key = hashlib.sha256(chave.encode("utf-8")).hexdigest()
    nonce = uuid.uuid4()
    prazo = timezone.now() + PRAZO
    linha, _ = RecuperacaoSenha.objects.get_or_create(
        identidade=identidade, pedido_key=pedido_key,
        defaults={"id": nonce, "token_hash": _digest(_token_da_linha(nonce)), "expira_em": prazo},
    )
    if linha.consumida_em is not None or linha.expira_em <= timezone.now():
        raise HttpError(409, "este pedido de recuperação já foi usado ou expirou")
    token = _token_da_linha(linha.id)
    return {"caminho": reverse("recuperar_senha") + "#" + token,
            "expira_em": linha.expira_em.isoformat()}


@require_http_methods(["GET", "POST"])
def recuperar_senha(request):
    # O fragmento do link não atravessa o GET nem entra em caminhos de acesso.
    # O navegador o põe somente no corpo deste POST, protegido pelo CSRF normal.
    resposta = None
    token = (request.POST.get("token") or "") if request.method == "POST" else ""
    registro = (RecuperacaoSenha.objects.filter(token_hash=_digest(token)).first()
                if FORMA_TOKEN.fullmatch(token) else None)
    valido = (request.method == "GET" or bool(
        registro and registro.consumida_em is None and registro.expira_em > timezone.now()))
    if request.method == "POST" and valido:
        nova = request.POST.get("senha") or ""
        confirmacao = request.POST.get("confirmacao") or ""
        erros = []
        if not nova:
            erros = ["Informe uma nova senha."]
        elif nova != confirmacao:
            erros = ["As senhas não conferem."]
        else:
            try:
                validate_password(nova)
            except ValidationError as erro:
                erros = erro.messages
        if not erros:
            with transaction.atomic():
                travado = RecuperacaoSenha.objects.select_for_update().get(pk=registro.pk)
                if travado.consumida_em is None and travado.expira_em > timezone.now():
                    pessoa = Identidade.objects.select_for_update().get(pk=travado.identidade_id)
                    pessoa.senha_hash = make_password(nova)
                    pessoa.save(update_fields=["senha_hash"])
                    travado.consumida_em = timezone.now()
                    travado.save(update_fields=["consumida_em"])
                    resposta = HttpResponseRedirect("/login")
                else:
                    valido = False
        if resposta is None and valido:
            resposta = render(request, "identidade/recuperar_senha.html",
                              {"valido": True, "erros": erros, "token": token})
    if resposta is None:
        resposta = render(request, "identidade/recuperar_senha.html", {"valido": valido},
                          status=200 if valido else 400)
    resposta["Cache-Control"] = "no-store"
    resposta["Referrer-Policy"] = "no-referrer"
    return resposta
