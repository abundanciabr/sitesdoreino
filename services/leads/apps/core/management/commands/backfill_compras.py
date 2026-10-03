"""Registra as compras já guardadas na linha do tempo, uma receita por pedido.

Pode rodar de novo: cada pedido vira uma linha só, e cada fato a muda uma vez.
"""

import uuid

from django.core.management.base import BaseCommand

from apps.core.compras import reconstruir_compras
from apps.core.models import CompraDaOportunidade, TimelineEvent
from apps.core.recuperacao import sincronizar_reversao


class Command(BaseCommand):
    help = "Liga pedidos e pagamentos já guardados à oportunidade certa"

    def add_arguments(self, parser):
        parser.add_argument("--site-id", default="")

    def handle(self, *args, **options):
        eventos = TimelineEvent.objects.all()
        if options["site_id"]:
            eventos = eventos.filter(lead__site_id=options["site_id"])
        reconstruir_compras(eventos)
        for evento in eventos.select_related("lead").filter(
            event="pagamento.reversao_confirmada"
        ).iterator():
            identidade = evento.event_id or uuid.uuid5(
                uuid.NAMESPACE_URL,
                f"reversao:{evento.lead.site_id}:{evento.payload.get('order_id')}",
            )
            sincronizar_reversao(identidade, evento.payload)
        compras = CompraDaOportunidade.objects.all()
        if options["site_id"]:
            compras = compras.filter(site_id=options["site_id"])
        self.stdout.write(
            f"Compras: {compras.count()}; aprovadas: "
            f"{compras.filter(aprovado_em__isnull=False).count()}; ligadas a "
            f"oportunidade: {compras.filter(oportunidade__isnull=False).count()}"
        )
