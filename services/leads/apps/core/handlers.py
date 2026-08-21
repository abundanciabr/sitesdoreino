# apps/core/handlers.py  # [RECEITA:R4 v1]
from django.db import IntegrityError, transaction

from .models import EventoProcessado, Lead, TimelineEvent


def processar_envelope(envelope: dict, handler) -> bool:
    """[INV-leads-idempotencia] Reentrega do mesmo event_id não roda o handler de
    novo. Retorna True se o handler rodou, False se o evento já havia sido
    processado antes (dedup, não erro).

    São DUAS transações aninhadas. Parecem redundantes; não são — cada uma fecha
    um modo de falha diferente, e remover qualquer uma reabre um bug silencioso.
    Guarda das duas: tests/test_inv_leads_evento_atomico.py.

    (1) A EXTERNA envolve o registro E o efeito, para que falhem juntos. Se o
        handler estourar (deadlock, conexão caída, timeout), o EventoProcessado
        é desfeito junto e a reentrega volta a funcionar. Com o create()
        commitando sozinho — como era antes —, um hiccup do Postgres no meio da
        gravação da timeline deixava o evento marcado como visto: toda reentrega
        futura caía no `except IntegrityError` abaixo e era descartada em
        silêncio, deixando um buraco permanente na história daquela pessoa. E a
        timeline é justamente o que esta célula existe para não perder.

    (2) A INTERNA é savepoint SÓ em volta do create(), por dois motivos.
        Primeiro, o savepoint em si (ver a primeira lição do LICOES.md desta
        célula e ARMADILHAS.md §4.8): sem ele, o IntegrityError do event_id
        duplicado marca a transação inteira como abortada e a query seguinte
        estoura TransactionManagementError. Segundo — e é por isso que o handler
        está FORA do try, não só fora do savepoint —, o `except` precisa
        enxergar exclusivamente o IntegrityError DESTE create. Aqui isso não é
        hipótese: `_upsert_lead()` usa get_or_create() sobre a constraint
        uniq_lead_site_email, que sob corrida levanta IntegrityError de verdade.
        Com o handler dentro do try, essa colisão seria lida como "já
        processado" e o evento sumiria em silêncio — o mesmo bug de antes, só
        que mais difícil de enxergar.
    """
    with transaction.atomic():  # (1) registro e efeito: vivem ou morrem juntos
        try:
            with transaction.atomic():  # (2) savepoint: SÓ o create
                EventoProcessado.objects.create(event_id=envelope["event_id"])
        except IntegrityError:
            return False  # já processado: nada foi gravado, o handler não roda
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
