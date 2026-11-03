"""Recibo, encaminhamento e uso único do acesso autorizado à escola."""
import hmac
import os
import re
from django.db import transaction
from django.db.models import CharField, Func, Q, Value
from django.db.models.functions import Lower, Trim
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

class ConsultaRecuperacaoWhatsApp(Schema):
    site_id: str
    telefone: str
    email_da_ficha: str = ""


@router.post("/acesso-alunos/resolver-whatsapp", include_in_schema=False)
def resolver_whatsapp(request, dados: ConsultaRecuperacaoWhatsApp):
    if not request.auth or request.auth != os.environ.get("TOKENS_ACEITOS_ADMIN"):
        raise HttpError(403, "somente a recuperação de acesso pode consultar")
    numero = re.sub(r"[^0-9]", "", dados.telefone)
    if len(numero) in (10, 11):
        numero = "55" + numero
    ausente = {"encontrado": False}
    if not dados.site_id or len(dados.site_id) > 64 or not re.fullmatch(r"[1-9][0-9]{9,14}", numero):
        return ausente

    site = Q(site_id=dados.site_id)
    if dados.site_id == "cc06b8c3-043b-4c06-92c5-5ea624e00586":
        site |= Q(site_id__iexact="Meshcraft")
    matriculas = Matricula.objects.filter(site, em_teste=False)
    telefones = [numero]
    if numero.startswith("55") and len(numero) in (12, 13):
        telefones.append(numero[2:])
    com_numero = matriculas.annotate(
        telefone_limpo=Func("whatsapp", Value("[^0-9]"), Value(""), Value("g"),
                           function="regexp_replace", output_field=CharField()),
        email_normalizado=Lower(Trim("email")),
    ).filter(telefone_limpo__in=telefones)
    emails = set(com_numero.values_list("email_normalizado", flat=True).distinct()[:2])
    email_da_ficha = dados.email_da_ficha.strip().lower()
    if email_da_ficha:
        emails.add(email_da_ficha)
    if len(emails) != 1:
        return ausente
    email = emails.pop()
    if not email:
        return ausente

    # A ficha legada pode completar uma matrícula sem telefone. Um telefone
    # diferente na matrícula ativa nunca é substituído pelo telefone da ficha.
    ativas = matriculas.filter(email__iexact=email, status=Matricula.STATUS_ATIVA)
    if not com_numero.filter(email_normalizado=email, status=Matricula.STATUS_ATIVA).exists():
        if not email_da_ficha or com_numero.exists() or not ativas.exists() or ativas.exclude(whatsapp="").exists():
            return ausente
    return {"encontrado": True, "email": email, "destino": numero}


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
