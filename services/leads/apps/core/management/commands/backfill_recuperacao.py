"""Reconstrói oportunidades dos eventos já guardados, sem remover registros."""

import uuid

from django.core.management.base import BaseCommand

from apps.core.models import TimelineEvent
from apps.core.recuperacao import sincronizar_pagamento, sincronizar_reversao


class Command(BaseCommand):
    help = "Cria oportunidades de recuperação a partir da timeline existente"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", default="")

    def handle(self, *args, **options):
        eventos = TimelineEvent.objects.select_related("lead").filter(
            event__in=["pagamento.recusado", "pix.expirado"]
        ).order_by("occurred_at", "id")
        if options["site_id"]:
            eventos = eventos.filter(lead__site_id=options["site_id"])
        criadas = 0
        for evento in eventos.iterator():
            antes = evento.lead.oportunidades.filter(
                fonte_tipo="pagamento",
                fonte_referencia_id=f"recuperar:{evento.payload.get('order_id')}",
            ).exists()
            oportunidade = sincronizar_pagamento(
                evento.lead, evento.event, evento.payload, evento.event_id or evento.id,
                evento,
            )
            criadas += int(oportunidade is not None and not antes)
        reversoes = TimelineEvent.objects.select_related("lead").filter(
            event="pagamento.reversao_confirmada"
        )
        if options["site_id"]:
            reversoes = reversoes.filter(lead__site_id=options["site_id"])
        for evento in reversoes.iterator():
            identidade = evento.event_id or uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"reversao:{evento.lead.site_id}:{evento.payload.get('order_id')}",
            )
            sincronizar_reversao(identidade, evento.payload)
        self.stdout.write(f"Oportunidades criadas: {criadas}")
