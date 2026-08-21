# apps/core/handlers.py  # [RECEITA:R4 v1]
from django.db import IntegrityError, transaction

from .models import EventoProcessado, Lead, TimelineEvent


def processar_envelope(envelope: dict, handler) -> bool:
    """[INV-leads-idempotencia] Reentrega do mesmo event_id não roda o handler de
    novo. Retorna True se o handler rodou, False se o evento já havia sido
    processado antes (dedup, não erro)."""
    try:
        with transaction.atomic():  # savepoint: sem isso, o IntegrityError deixa
            EventoProcessado.objects.create(
                event_id=envelope["event_id"]
            )  # a conexão inteira "quebrada" fora do bloco
    except IntegrityError:
        return False
    handler(envelope["event_id"], envelope["data"])
    return True


def _upsert_lead(
    *,
    site_id: str,
    email: str,
    name: str = "",
    phone: str = "",
    source: str = "",
    utm: dict | None = None,
) -> Lead:
    """Upsert por (site_id, email). Nunca apaga o que já existia — só acrescenta
    ou atualiza campos vindos com valor."""
    lead, criado = Lead.objects.get_or_create(
        site_id=site_id,
        email=email,
        defaults={"name": name, "phone": phone, "source": source, "utm": utm or {}},
    )
    if not criado:
        campos = []
        if name and lead.name != name:
            lead.name = name
            campos.append("name")
        if phone and lead.phone != phone:
            lead.phone = phone
            campos.append("phone")
        if campos:
            lead.save(update_fields=campos)
    return lead


def ao_quiz_completado(event_id: str, data: dict) -> None:
    with transaction.atomic():
        pessoa = data["lead"]
        lead = _upsert_lead(
            site_id=data["site_id"],
            email=pessoa["email"],
            name=pessoa.get("name", ""),
            phone=pessoa.get("phone", ""),
            source=f"quiz:{data['quiz_slug']}",
            utm=data.get("utm"),
        )
        TimelineEvent.objects.create(
            lead=lead, event="quiz.completado", event_id=event_id, payload=data
        )


def ao_pedido_criado(event_id: str, data: dict) -> None:
    with transaction.atomic():
        cliente = data["customer"]
        lead = _upsert_lead(
            site_id=data["site_id"],
            email=cliente["email"],
            name=cliente.get("name", ""),
            phone=cliente.get("phone", ""),
            utm=data.get("utm"),
        )
        TimelineEvent.objects.create(
            lead=lead, event="pedido.criado", event_id=event_id, payload=data
        )


def ao_pagamento_aprovado(event_id: str, data: dict) -> None:
    with transaction.atomic():
        cliente = data["customer"]
        lead = _upsert_lead(
            site_id=data["site_id"],
            email=cliente["email"],
            name=cliente.get("name", ""),
            phone=cliente.get("phone", ""),
        )
        TimelineEvent.objects.create(
            lead=lead, event="pagamento.aprovado", event_id=event_id, payload=data
        )


def ao_pagamento_recusado(event_id: str, data: dict) -> None:
    with transaction.atomic():
        cliente = data["customer"]
        lead = _upsert_lead(
            site_id=data["site_id"],
            email=cliente["email"],
            name=cliente.get("name", ""),
            phone=cliente.get("phone", ""),
        )
        TimelineEvent.objects.create(
            lead=lead, event="pagamento.recusado", event_id=event_id, payload=data
        )


def ao_pix_expirado(event_id: str, data: dict) -> None:
    with transaction.atomic():
        cliente = data["customer"]
        lead = _upsert_lead(
            site_id=data["site_id"],
            email=cliente["email"],
            name=cliente.get("name", ""),
            phone=cliente.get("phone", ""),
        )
        TimelineEvent.objects.create(
            lead=lead, event="pix.expirado", event_id=event_id, payload=data
        )
