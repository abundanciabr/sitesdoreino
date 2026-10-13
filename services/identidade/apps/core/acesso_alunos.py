"""Códigos da recuperação pública; somente o par admin resolve o CRM e os emite."""
import os
import re
import secrets
import uuid
import hmac
from datetime import timedelta
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from apps.identidade.models import Identidade, AcessoPrevia
from . import sessao
from .acesso_previa import _hash, _resumo

router = Router()
class Preparar(Schema):
    site_id: str
    email: str
    canal: str
    destino: str
    vinculo: str
class Confirmar(Schema):
    site_id: str
    desafio: str
    codigo: str
    vinculo: str

def admin(request):
    token = os.environ.get("TOKENS_ACEITOS_ADMIN", "")
    if not token or request.auth != token or token not in settings.TOKENS_SENHA:
        raise HttpError(403, "Pedido não autorizado.")

def vinculo_valido(valor):
    return bool(re.fullmatch(r"[A-Za-z0-9_-]{40,100}", valor))

@router.post("/acesso-alunos/preparar")
def preparar(request, dados: Preparar):
    admin(request)
    email = dados.email.strip().lower()
    destino = dados.destino.strip().lower()
    if not vinculo_valido(dados.vinculo) or not dados.site_id or len(dados.site_id)>100:
        raise HttpError(422, "Pedido inválido.")
    if dados.canal not in {"email", "whatsapp"} or (dados.canal == "email" and destino != email) or (dados.canal == "whatsapp" and not re.fullmatch(r"[1-9][0-9]{9,14}", destino)):
        raise HttpError(422, "Pedido inválido.")
    agora = timezone.now()
    with transaction.atomic():
        pessoa = Identidade.objects.select_for_update().filter(email__iexact=email).first()
        if not pessoa: return {"encontrado":False}
        # O telefone de uma captura comercial não recupera contas administrativas.
        if dados.canal == "whatsapp" and sessao.e_staff(pessoa.email):
            return {"encontrado":False}
        anteriores = AcessoPrevia.objects.filter(identidade=pessoa, criado_em__gte=agora-timedelta(hours=1))
        if anteriores.count()>=5 or anteriores.filter(criado_em__gte=agora-timedelta(seconds=60)).exists():
            raise HttpError(429, "Aguarde antes de pedir outro código.")
        codigo = f"{secrets.randbelow(1000000):06d}"
        desafio = AcessoPrevia(identidade=pessoa,site_id=dados.site_id,canal=dados.canal,destino=destino,expira_em=agora+timedelta(minutes=10))
        desafio.codigo_hash = _hash(desafio.id, codigo)
        desafio.vinculo_hash = _hash(desafio.id, dados.vinculo)
        desafio.save()
    return {"encontrado":True, **_resumo(desafio), "codigo":codigo,"destino":destino}

@router.post("/acesso-alunos/confirmar")
def confirmar(request, dados: Confirmar):
    admin(request)
    try: uuid.UUID(dados.desafio)
    except (ValueError, AttributeError): raise HttpError(400,"Código inválido ou expirado.") from None
    if not vinculo_valido(dados.vinculo): raise HttpError(400,"Código inválido ou expirado.")
    correto = False
    with transaction.atomic():
        d = AcessoPrevia.objects.select_for_update().filter(pk=dados.desafio,site_id=dados.site_id).first()
        if d and d.vinculo_hash and hmac.compare_digest(d.vinculo_hash,_hash(d.id,dados.vinculo)) and d.consumido_em is None and d.expira_em>timezone.now() and d.tentativas<5:
            d.tentativas += 1
            correto = bool(re.fullmatch(r"[0-9]{6}",dados.codigo)) and hmac.compare_digest(d.codigo_hash,_hash(d.id,dados.codigo))
            if correto: d.consumido_em = timezone.now()
            d.save(update_fields=["tentativas","consumido_em"])
    if not correto: raise HttpError(400,"Código inválido, expirado ou já utilizado. Solicite outro se necessário.")
    sessao.abrir_sessao(request,d.identidade)
    request.session.save()
    return {"sessao":request.session.session_key,"max_age":request.session.get_expiry_age()}
