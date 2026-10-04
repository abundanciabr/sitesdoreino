"""`POST /avisos-equipe`: o painel pede um e-mail para uma pessoa da equipe.

É o mesmo caminho de todo e-mail desta célula: a linha em `EnvioRegistrado`
(auditoria e idempotência) e a task `enviar_notificacao`, que fala com o
provedor, retenta e respeita endereço bloqueado. Nada de transporte novo.

Idempotente pela `chave` que o painel manda (um aviso, um destinatário): pedir
duas vezes devolve a mesma linha e não manda o e-mail de novo.
"""

from __future__ import annotations

import hashlib

from django.db import transaction
from ninja import Router, Schema
from ninja.errors import HttpError

from apps.core.api import _exige_grau_de_publicacao

from .models import EnvioRegistrado
from .tasks import enviar_notificacao

router = Router()

TIPO = "aviso_equipe"
EVENTO = "aviso.equipe"


class PedidoDeAviso(Schema):
    site_id: str = ""
    chave: str
    destinatario: str
    assunto: str
    corpo: str


class AvisoRegistrado(Schema):
    envio_id: int
    criado: bool
    status: str


def _referencia(chave: str) -> str:
    # `order_id` tem 100 caracteres; a chave do painel pode ser maior. O hash
    # mantém a mesma chave na mesma linha sem cortar uma chave em duas.
    limpa = chave.strip()
    if len(limpa) <= 100:
        return limpa
    return "aviso-" + hashlib.sha256(limpa.encode("utf-8")).hexdigest()[:64]


@router.post(
    "/avisos-equipe",
    response=AvisoRegistrado,
    operation_id="enviarAvisoParaEquipe",
    summary="Manda por e-mail um aviso do painel para uma pessoa da equipe",
)
def enviar_aviso_para_equipe(request, dados: PedidoDeAviso):
    _exige_grau_de_publicacao(request)
    chave = (dados.chave or "").strip()
    destinatario = (dados.destinatario or "").strip().lower()
    assunto = (dados.assunto or "").strip()
    corpo = dados.corpo or ""
    if not chave:
        raise HttpError(422, "chave ausente")
    if "@" not in destinatario:
        raise HttpError(422, "destinatario precisa ser um e-mail")
    if not assunto or not corpo.strip():
        raise HttpError(422, "assunto e corpo sao obrigatorios")
    site_id = (dados.site_id or "").strip() or "equipe"
    with transaction.atomic():
        envio, criado = EnvioRegistrado.objects.get_or_create(
            site_id=site_id,
            order_id=_referencia(chave),
            tipo=TIPO,
            canal="email",
            defaults=dict(
                event=EVENTO,
                destinatario=destinatario,
                assunto=assunto[:255],
                corpo=corpo,
            ),
        )
        if criado:
            transaction.on_commit(lambda: enviar_notificacao(envio.id))
    return AvisoRegistrado(envio_id=envio.id, criado=criado, status=envio.status)
