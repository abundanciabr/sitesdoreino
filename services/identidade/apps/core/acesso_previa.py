"""OTP para ensaio privado iniciado e confirmado pelo admin da própria conta."""
import hashlib
import hmac
import os
import re
import secrets
import uuid
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from apps.core import sessao
from apps.identidade.models import Identidade, AcessoPrevia

router = Router()

class Preparar(Schema):
    site_id: str
    canal: str
    destino: str

class Confirmar(Schema):
    site_id: str
    desafio: str
    codigo: str

def _pessoa(request):
    # O par ADMIN já tem permissão de senha, e precisa também apresentar a
    # sessão existente da pessoa. Não aceita ID/e-mail escolhido pelo chamador.
    autorizado = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    if not autorizado or request.auth != autorizado or request.auth not in settings.TOKENS_SENHA:
        raise HttpError(403, "Prévia restrita ao painel administrativo.")
    ator = sessao.ator_atual(request)
    if ator is None:
        raise HttpError(403, "Entre também na sua conta do site para testar.")
    return ator.identidade

def _hash(chave, codigo):
    return hmac.new(settings.SECRET_KEY.encode(), f"acesso-previa:{chave}:{codigo}".encode(), hashlib.sha256).hexdigest()

def _mascara(canal, destino):
    if canal == "whatsapp":
        return "•••• " + destino[-4:]
    nome, dominio = destino.split("@", 1)
    return nome[:1] + "•••@" + dominio

def _resumo(desafio):
    return {"desafio": str(desafio.id), "canal": desafio.canal,
            "destino_mascarado": _mascara(desafio.canal, desafio.destino),
            "expira_em": desafio.expira_em.isoformat()}

@router.get("/acesso-previa/estado")
def estado(request, site_id: str):
    pessoa = _pessoa(request)
    atual = AcessoPrevia.objects.filter(identidade=pessoa, site_id=site_id,
        consumido_em__isnull=True, expira_em__gt=timezone.now(), tentativas__lt=5).order_by("-criado_em").first()
    return {"id": pessoa.id, "email": pessoa.email, "desafio": _resumo(atual) if atual else None}

@router.post("/acesso-previa/preparar")
def preparar(request, dados: Preparar):
    pessoa = _pessoa(request)
    destino = dados.destino.strip().lower()
    if not dados.site_id or len(dados.site_id) > 100 or dados.canal not in {"email", "whatsapp"}:
        raise HttpError(422, "Canal ou site inválido.")
    if dados.canal == "email":
        if destino != pessoa.email.strip().lower():
            raise HttpError(422, "Use o e-mail da sua conta atual; a prévia não troca nem cria contas.")
    else:
        destino = re.sub(r"[\s()+-]", "", destino)
        if not re.fullmatch(r"[1-9][0-9]{9,14}", destino):
            raise HttpError(422, "Informe seu WhatsApp com DDI e DDD.")
    agora = timezone.now()
    with transaction.atomic():
        Identidade.objects.select_for_update().get(pk=pessoa.pk)
        anteriores = AcessoPrevia.objects.filter(identidade=pessoa, criado_em__gte=agora-timedelta(hours=1))
        if anteriores.count() >= 5 or anteriores.filter(criado_em__gte=agora-timedelta(seconds=60)).exists():
            raise HttpError(429, "Aguarde antes de pedir outro código. Até cinco pedidos por hora.")
        # Registra a expiração, preservando o histórico dos desafios anteriores.
        AcessoPrevia.objects.filter(identidade=pessoa, consumido_em__isnull=True, expira_em__gt=agora).update(expira_em=agora)
        codigo = f"{secrets.randbelow(1000000):06d}"
        desafio = AcessoPrevia(identidade=pessoa, site_id=dados.site_id, canal=dados.canal,
            destino=destino, expira_em=agora+timedelta(minutes=10))
        desafio.codigo_hash = _hash(desafio.id, codigo)
        desafio.save()
    # Segredo somente entre serviços para envio. Nunca segue ao HTML/log.
    return {**_resumo(desafio), "codigo": codigo, "destino": destino}

@router.post("/acesso-previa/confirmar")
def confirmar(request, dados: Confirmar):
    pessoa = _pessoa(request)
    try:
        uuid.UUID(dados.desafio)
    except (ValueError, AttributeError):
        raise HttpError(400, "Código inválido ou expirado.") from None
    correto = False
    with transaction.atomic():
        desafio = AcessoPrevia.objects.select_for_update().filter(pk=dados.desafio,
            identidade=pessoa, site_id=dados.site_id).first()
        if desafio and desafio.consumido_em is None and desafio.expira_em > timezone.now() and desafio.tentativas < 5:
            desafio.tentativas += 1
            correto = bool(re.fullmatch(r"[0-9]{6}", dados.codigo)) and hmac.compare_digest(
                desafio.codigo_hash, _hash(desafio.id, dados.codigo))
            if correto:
                desafio.consumido_em = timezone.now()
            desafio.save(update_fields=["tentativas", "consumido_em"])
    if not correto:
        raise HttpError(400, "Código inválido, expirado ou já utilizado.")
    sessao.abrir_sessao(request, pessoa)
    request.session.save()
    return {"id": pessoa.id, "sessao": request.session.session_key,
            "max_age": request.session.get_expiry_age(), "canal": desafio.canal,
            "destino_mascarado": _mascara(desafio.canal, desafio.destino)}
