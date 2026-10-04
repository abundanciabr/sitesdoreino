"""Reconstrói oportunidades dos eventos já guardados, sem remover registros."""

import uuid

from django.core.management.base import BaseCommand

from apps.core.compras import reconstruir_compras
from apps.core.models import Oportunidade, TimelineEvent
from apps.core.recuperacao import sincronizar_reversao


class Command(BaseCommand):
    help = "Cria oportunidades de recuperação a partir da timeline existente"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", default="")

    def handle(self, *args, **options):
        eventos = TimelineEvent.objects.all()
        if options["site_id"]:
            eventos = eventos.filter(lead__site_id=options["site_id"])
        antes = Oportunidade.objects.filter(fonte_tipo="pagamento").count()
        reconstruir_compras(eventos)
        reversoes = eventos.select_related("lead").filter(
            event="pagamento.reversao_confirmada"
        )
        for evento in reversoes.iterator():
            identidade = evento.event_id or uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"reversao:{evento.lead.site_id}:{evento.payload.get('order_id')}",
            )
            sincronizar_reversao(identidade, evento.payload)
        criadas = Oportunidade.objects.filter(fonte_tipo="pagamento").count() - antes
        self.stdout.write(f"Oportunidades criadas: {criadas}")
