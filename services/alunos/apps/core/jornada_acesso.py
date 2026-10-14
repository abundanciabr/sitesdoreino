"""Recibo, encaminhamento e uso único do acesso autorizado à escola."""
import hmac
import os
import re
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError
from apps.matriculas.models import Matricula
from apps.matriculas.avisos_acesso import token_de_acesso
from apps.matriculas.services import decidir_na_fila

router = Router()

def contato(linha):
    return {"site_id": linha.site_id, "matricula_id": str(linha.pk),
        "email": linha.email, "nome": linha.name, "whatsapp": linha.whatsapp,
        "whatsapp_avisos": linha.whatsapp_avisos,
        "whatsapp_confirmado": bool(linha.whatsapp_confirmado_em),
        "whatsapp_consentido_em": linha.whatsapp_consentido_em.isoformat() if linha.whatsapp_consentido_em else None,
        "status": linha.status, "motivo": linha.motivo_recusa,
        "resolvido": bool(linha.suporte_resolvido_em)}

@router.get("/avisos-acesso/recibo")
def recibo(request, site_id: str, event_id: str):
    linha = Matricula.objects.filter(site_id=site_id, recibo_event_id=event_id).first()
    if not linha: raise HttpError(404, "pedido substituído")
    return {**contato(linha), "event_id": str(linha.recibo_event_id)}

@router.get("/avisos-acesso/suporte")
def suporte(request, site_id: str, event_id: str):
    linha = Matricula.objects.filter(site_id=site_id, suporte_event_id=event_id).first()
    if not linha: raise HttpError(404, "encaminhamento substituído")
    return {**contato(linha), "event_id": str(linha.suporte_event_id)}

class Resolver(Schema):
    site_id: str
    event_id: str
    decisao: str
    decidido_por: str
    motivo: str = ""
    product_id: str = ""

@router.post("/pre-matriculas/{id}/suporte")
def resolver(request, id: str, dados: Resolver):
    if request.auth != os.environ.get("TOKENS_ACEITOS_ADMIN") or not request.auth:
        raise HttpError(403, "somente o atendimento da escola pode resolver")
    linha = Matricula.objects.filter(pk=id, site_id=dados.site_id, suporte_event_id=dados.event_id).first()
    if not linha: raise HttpError(404, "encaminhamento substituído")
    if dados.decisao not in ("liberar", "recusar") or not dados.decidido_por.strip():
        raise HttpError(422, "confira a decisão e o responsável")
    if dados.decisao == "recusar" and not dados.motivo.strip():
        raise HttpError(422, "explique o motivo ao aluno")
    linha, resultado = decidir_na_fila(id_da_linha=id, decisao=dados.decisao,
        decidido_por=dados.decidido_por, motivo=dados.motivo.strip(), product_id=dados.product_id,
        pelo_suporte=True)
    if resultado != "ok": raise HttpError(409, resultado)
    return {"id": str(linha.pk), "status": linha.status, "resolvido": True}

class Consumir(Schema):
    token: str

@router.post("/acesso-escola/consumir", auth=None)
def consumir(request, dados: Consumir):
    # A credencial desta operação é o próprio token de alta entropia, de uso único.
    # Não aceita e-mail, identidade ou matrícula escolhidos pelo chamador.
    if not re.fullmatch(r"[0-9]+\.[0-9a-f]{32}\.[0-9a-f]{64}", dados.token):
        raise HttpError(400, "link inválido ou já utilizado")
    chave, evento, _ = dados.token.split(".")
    with transaction.atomic():
        linha = Matricula.objects.select_for_update().filter(pk=chave,
            order_id__startswith=Matricula.PREFIXO_DA_FILA, status=Matricula.STATUS_ATIVA).first()
        if (not linha or linha.acesso_consumido_em or not linha.aviso_event_id
                or linha.aviso_event_id.hex != evento or not hmac.compare_digest(token_de_acesso(linha), dados.token)):
            raise HttpError(400, "link inválido ou já utilizado")
        linha.acesso_consumido_em = timezone.now()
        linha.save(update_fields=["acesso_consumido_em"])
    return {"site_id": linha.site_id, "email": linha.email, "nome": linha.name}
